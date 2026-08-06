#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用 PaddleOCR-VL API 识别施工照片（今日水印照片），输出 Markdown 文本。

用法：
    python scripts/paddleocr_to_text.py <图片路径或URL> [<更多图片>] [--token TOKEN] [--out-dir output]

说明：
- 支持本地图片路径或 http(s) 图片 URL，可一次传多张。
- 每张图片识别结果保存为 output/doc_N.md，并在 stdout 打印识别文本，
  供后续解析标段/桩号/工序并生成施工日志 Word。
- 依赖：pip install requests
"""

import argparse
import json
import os
import sys
import time

import requests

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
DEFAULT_TOKEN = "13c2a79aa77099de0e18c96ee65e162a9b91fae0"
MODEL = "PaddleOCR-VL-1.6"

OPTIONAL_PAYLOAD = {
    "useDocOrientationClassify": False,
    "useDocUnwarping": False,
    "useChartRecognition": False,
}


def submit_job(file_path, token, headers):
    """提交识别任务，返回 jobId。"""
    if file_path.startswith("http"):
        headers["Content-Type"] = "application/json"
        payload = {
            "fileUrl": file_path,
            "model": MODEL,
            "optionalPayload": OPTIONAL_PAYLOAD,
        }
        resp = requests.post(JOB_URL, json=payload, headers=headers)
    else:
        if not os.path.exists(file_path):
            print(f"Error: File not found at {file_path}")
            sys.exit(1)
        data = {
            "model": MODEL,
            "optionalPayload": json.dumps(OPTIONAL_PAYLOAD),
        }
        with open(file_path, "rb") as f:
            resp = requests.post(JOB_URL, headers=headers, data=data, files={"file": f})

    print(f"Response status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Response content: {resp.text}")
    assert resp.status_code == 200
    job_id = resp.json()["data"]["jobId"]
    print(f"Job submitted successfully. job id: {job_id}")
    return job_id


def poll_result(job_id, token, headers):
    """轮询任务状态，返回结果 JSONL 的 URL。"""
    while True:
        resp = requests.get(f"{JOB_URL}/{job_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        state = data["state"]
        if state == "pending":
            print("The current status of the job is pending")
        elif state == "running":
            try:
                total = data["extractProgress"]["totalPages"]
                done = data["extractProgress"]["extractedPages"]
                print(f"The current status of the job is running, total pages: {total}, extracted pages: {done}")
            except KeyError:
                print("The current status of the job is running...")
        elif state == "done":
            ep = data["extractProgress"]
            print(f"Job completed, successfully extracted pages: {ep['extractedPages']}, "
                  f"start time: {ep['startTime']}, end time: {ep['endTime']}")
            return data["resultUrl"]["jsonUrl"]
        elif state == "failed":
            print(f"Job failed, failure reason: {data.get('errorMsg')}")
            sys.exit(1)
        time.sleep(5)


def save_results(jsonl_url, out_dir):
    """下载结果，保存 Markdown 文本与图片，返回识别文本列表。"""
    resp = requests.get(jsonl_url)
    resp.raise_for_status()
    lines = resp.text.strip().split("\n")
    os.makedirs(out_dir, exist_ok=True)
    texts = []
    page_num = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        result = json.loads(line)["result"]
        for res in result["layoutParsingResults"]:
            md_filename = os.path.join(out_dir, f"doc_{page_num}.md")
            with open(md_filename, "w", encoding="utf-8") as f:
                f.write(res["markdown"]["text"])
            texts.append(res["markdown"]["text"])
            print(f"Markdown document saved at {md_filename}")
            for img_path, img in res["markdown"]["images"].items():
                full_img_path = os.path.join(out_dir, img_path)
                os.makedirs(os.path.dirname(full_img_path), exist_ok=True)
                img_bytes = requests.get(img).content
                with open(full_img_path, "wb") as img_file:
                    img_file.write(img_bytes)
                print(f"Image saved to: {full_img_path}")
            for img_name, img in res["outputImages"].items():
                img_response = requests.get(img)
                if img_response.status_code == 200:
                    filename = os.path.join(out_dir, f"{img_name}_{page_num}.jpg")
                    with open(filename, "wb") as f:
                        f.write(img_response.content)
                    print(f"Image saved to: {filename}")
                else:
                    print(f"Failed to download image, status code: {img_response.status_code}")
            page_num += 1
    return texts


def main():
    parser = argparse.ArgumentParser(description="PaddleOCR-VL 识别施工照片")
    parser.add_argument("files", nargs="+", help="本地图片路径或图片 URL")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="PaddleOCR API token")
    parser.add_argument("--out-dir", default="output", help="识别结果输出目录")
    args = parser.parse_args()

    headers = {"Authorization": f"bearer {args.token}"}
    for fp in args.files:
        print(f"\nProcessing file: {fp}")
        job_id = submit_job(fp, args.token, headers)
        jsonl_url = poll_result(job_id, args.token, headers)
        texts = save_results(jsonl_url, args.out_dir)
        for i, t in enumerate(texts):
            print(f"\n===== 识别文本 [{i}] =====")
            print(t)


if __name__ == "__main__":
    main()
