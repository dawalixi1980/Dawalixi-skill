import { useSyncExternalStore } from "react";

// The playback clock, published OUTSIDE React state.
//
// A playing clip advances every frame. Routing that through useState would
// re-render the whole workspace per frame; instead the rAF loop publishes the
// elapsed time here and only the two consumers that need it per frame — the
// render pane (which hands the time down to the effects pass) and the Animation
// tab's time slider — subscribe. Everything else reads the paused elapsed time
// off the React animation state, which the loop writes once when playback stops.
//
// Time is the WHOLE snapshot: choreography is a pure function of t, so a
// consumer that knows t can rebuild the frame itself.

const listeners = new Set();

let elapsedSec = 0;

function subscribe(listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot() {
  return elapsedSec;
}

function normalizeElapsedSec(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) && numericValue > 0 ? numericValue : 0;
}

export function setAnimationClock(nextElapsedSec) {
  const next = normalizeElapsedSec(nextElapsedSec);
  if (next === elapsedSec) {
    return;
  }
  elapsedSec = next;
  for (const listener of listeners) {
    listener();
  }
}

export function resetAnimationClock() {
  setAnimationClock(0);
}

export function getAnimationClock() {
  return elapsedSec;
}

export function useAnimationClock() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
