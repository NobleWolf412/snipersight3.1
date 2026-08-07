/* SSWheel — a headless physics engine for a rotating carousel.

   HEADLESS ON PURPOSE. This file knows nothing about Mission Briefs, trades,
   or cards. It owns exactly one number — `pos`, a continuous position in
   item-units where 2.4 means "40% of the way from item 2 to item 3" — and it
   tells a consumer that number every frame. Everything visual, every
   transform, every piece of DOM is the consumer's business.

   That separation is the point. The same engine drives the mission rail
   today; a watchlist, a scan history or a Results carousel can drive off it
   tomorrow by passing a different onFrame. It also ports: a React host wraps
   this in a hook and re-exports `pos` as a motion value without the physics
   changing at all.

   WHAT IT IS NOT. It is not a slider and it is not a snap carousel. There are
   no pages and no discrete steps. A drag moves `pos` by exactly the distance
   the pointer moved, divided by the item pitch — one inch of finger is one
   inch of wheel, always. A release does not animate to a destination; it
   hands the wheel its release velocity and lets friction take it, and only
   once the wheel is genuinely slow does a spring gather it to the nearest
   detent. Fast flicks therefore cross several items and coast; slow drags
   barely move on. Nothing ever jumps.

   THE MODEL. A weighted wheel with a light detent, integrated at a fixed
   timestep so the feel does not change with frame rate:

     friction   per-second velocity retention while coasting (heavier = more)
     stiffness  how hard the detent pulls once coasting has decayed
     damping    how much that pull is resisted — tuned near critical so the
                wheel settles rather than bouncing. Elastic overshoot is
                explicitly not wanted here.

   Everything runs off one rAF loop that stops dead when the wheel is at rest,
   so an idle carousel costs nothing. */
(() => {
  'use strict';

  /* Fixed physics timestep. A variable dt integrated directly makes the same
     flick travel different distances on a 60Hz and a 144Hz screen, and makes
     a dropped frame feel like a shove. The accumulator decouples the physics
     rate from the paint rate; the leftover is carried, never discarded. */
  const STEP = 1000 / 120;
  const MAX_CATCHUP = 100;      // ms; a backgrounded tab must not integrate a
                                // thousand steps the instant it returns

  const DEFAULTS = {
    friction: 0.94,     // per 16.67ms of coast — lower stops sooner
    stiffness: 0.055,   // detent pull
    damping: 0.78,      // resistance to that pull; < 1, near-critical
    catchStiffness: 0.11,   // the firmer pull used by goTo()
    catchDamping: 0.72,
    minVel: 0.00006,    // item-units/ms below which coasting is over
    restVel: 0.00002,   // and below which the whole wheel is asleep
    settleGap: 0.0009,  // how close to a detent counts as arrived
    bound: 0.85,        // how far past the ends the wheel may be pulled
    wheelStep: 0.85,    // items per mouse-wheel notch
  };

  function create(surface, opts){
    const o = Object.assign({}, DEFAULTS, opts || {});
    /* `count` and `pitch` are read through functions, never captured, because
       both change under this engine's feet — cards arrive on a 30s poll and
       the pitch is a layout measurement that moves with the viewport. An
       engine holding a stale copy of either drifts a little further out of
       agreement with the DOM on every resize. */
    const count = () => Math.max(0, o.count ? o.count() : 0);
    const pitch = () => Math.max(1, o.pitch ? o.pitch() : 1);

    let pos = 0;            // continuous position, in item-units
    let vel = 0;            // item-units per ms
    let target = null;      // detent being sought, or null while free
    let raf = 0, lastT = 0, acc = 0;
    let dragging = false, moved = false, pid = null;
    let grabPos = 0, grabX = 0;
    let stiff = o.stiffness, damp = o.damping;
    /* Velocity is measured over a short trailing window rather than from the
       last two events. Pointer events arrive unevenly and the final one before
       release is frequently a near-duplicate — differencing just those two
       reports a flick as a dead stop, which is the classic "my throw did
       nothing" bug. */
    let samples = [];
    const VEL_WINDOW = 90;  // ms

    const maxPos = () => Math.max(0, count() - 1);
    const clampSoft = p => {
      const hi = maxPos();
      if(p < -o.bound) return -o.bound;
      if(p > hi + o.bound) return hi + o.bound;
      return p;
    };

    function emit(){
      if(o.onFrame) o.onFrame(pos, {vel, dragging, target});
    }

    function wake(){
      if(raf) return;
      lastT = performance.now(); acc = 0;
      raf = requestAnimationFrame(tick);
    }
    function sleep(){
      if(raf) cancelAnimationFrame(raf);
      raf = 0; acc = 0;
      if(o.onRest) o.onRest(pos);
    }

    /* One integration step. Three regimes, in order of authority: held by a
       pointer (physics suspended entirely — the wheel IS the finger), coasting
       on release velocity, or being gathered by the detent spring. */
    function step(){
      if(dragging) return;
      const hi = maxPos();

      // Past an end, the boundary always wins: it pulls back harder than the
      // detent and kills the coast, so the wheel cannot be flung off its rail.
      if(pos < 0 || pos > hi){
        const edge = pos < 0 ? 0 : hi;
        vel += (edge - pos) * 0.014;
        vel *= 0.72;
        pos += vel * STEP;
        if(Math.abs(pos - edge) < o.settleGap && Math.abs(vel) < o.restVel){
          pos = edge; vel = 0; target = null;
        }
        return;
      }

      const coasting = target === null && Math.abs(vel) > o.minVel;
      if(coasting){
        // Friction quoted per 60Hz frame, applied per fixed step, so the
        // constant means the same thing whatever the timestep is.
        vel *= Math.pow(o.friction, STEP / 16.667);
        pos += vel * STEP;
        return;
      }

      // Coast spent: gather to a detent. Chosen once, then held, so the wheel
      // cannot dither between two neighbours as it slows.
      if(target === null){
        target = Math.max(0, Math.min(hi, Math.round(pos)));
        stiff = o.stiffness; damp = o.damping;
      }
      const d = target - pos;
      vel += d * stiff * (STEP / 16.667);
      vel *= Math.pow(damp, STEP / 16.667);
      pos += vel * STEP;
      if(Math.abs(d) < o.settleGap && Math.abs(vel) < o.restVel){
        pos = target; vel = 0; target = null;
      }
    }

    function tick(now){
      raf = 0;
      let dt = now - lastT;
      lastT = now;
      if(dt > MAX_CATCHUP) dt = MAX_CATCHUP;
      acc += dt;
      let guard = 0;
      while(acc >= STEP && guard++ < 40){ step(); acc -= STEP; }
      emit();
      const asleep = !dragging && vel === 0 && target === null;
      if(asleep) sleep(); else raf = requestAnimationFrame(tick);
    }

    /* ---------- pointer ----------
       One handler set for mouse, pen and touch. `touch-action:pan-y` on the
       surface is what lets a vertical swipe scroll the page while a
       horizontal one turns the wheel, so the carousel never traps the page on
       a phone. */
    function onDown(e){
      if(e.button != null && e.button > 0) return;
      if(!count()) return;
      dragging = true; moved = false;
      pid = e.pointerId;
      grabPos = pos; grabX = e.clientX;
      vel = 0; target = null;
      samples = [{t: e.timeStamp || performance.now(), x: e.clientX}];
      wake();
    }
    function onMove(e){
      if(!dragging || e.pointerId !== pid) return;
      const dx = e.clientX - grabX;
      if(!moved && Math.abs(dx) > 3){
        moved = true;
        surface.classList.add('is-dragging');
        try { surface.setPointerCapture(pid); } catch (_){ /* already gone */ }
      }
      if(!moved) return;
      /* THE ATTACHMENT. Position follows the pointer exactly: pixels moved
         over pixels per item. No easing, no smoothing, no lag — smoothing here
         is precisely what makes a carousel feel detached from the finger.
         Beyond the ends it is rubber-banded rather than hard-stopped. */
      const raw = grabPos - dx / pitch();
      const hi = maxPos();
      pos = raw < 0 ? raw * 0.42
          : raw > hi ? hi + (raw - hi) * 0.42
          : raw;
      pos = clampSoft(pos);
      const t = e.timeStamp || performance.now();
      samples.push({t, x: e.clientX});
      while(samples.length > 2 && t - samples[0].t > VEL_WINDOW) samples.shift();
      wake();
    }
    function onUp(e){
      if(!dragging || (pid != null && e.pointerId !== pid)) return;
      dragging = false;
      surface.classList.remove('is-dragging');
      try { if(pid != null && surface.hasPointerCapture(pid)) surface.releasePointerCapture(pid); }
      catch (_){ /* nothing to release */ }
      pid = null;
      const first = samples[0], last = samples[samples.length - 1];
      const dt = last && first ? last.t - first.t : 0;
      // Below ~8ms the sample window is noise, not a measurement.
      vel = (moved && dt > 8) ? -((last.x - first.x) / dt) / pitch() : 0;
      target = null;
      samples = [];
      wake();
    }

    /* A drag must not fire the button it ended on. Capture phase, so the
       click is swallowed before it reaches anything inside. */
    function onClickCapture(e){
      if(!moved) return;
      e.stopPropagation(); e.preventDefault();
      moved = false;
    }

    function onWheel(e){
      if(!count()) return;
      /* Trackpads report horizontal intent; a plain mouse only ever reports
         vertical. Honour whichever axis is dominant so both hardware kinds
         turn the wheel, and leave the event alone when the gesture is really
         a vertical page scroll on a trackpad. */
      const horiz = Math.abs(e.deltaX) > Math.abs(e.deltaY);
      const raw = horiz ? e.deltaX : e.deltaY;
      if(!raw) return;
      if(!horiz && Math.abs(e.deltaY) < 4) return;
      e.preventDefault();
      const dir = raw > 0 ? 1 : -1;
      const mag = Math.min(1, Math.abs(raw) / 100);
      goTo(Math.round(pos) + dir * Math.max(1, Math.round(mag * o.wheelStep + 0.35)));
    }

    /* Seek a specific item under a firmer spring than the resting detent —
       this is a commanded move (an arrow key, a click on a side card), and it
       should arrive with intent rather than drift in. Still a spring, so it
       is continuous with whatever the wheel was already doing; a commanded
       move mid-coast blends instead of snapping. */
    function goTo(i, opt){
      const hi = maxPos();
      target = Math.max(0, Math.min(hi, Math.round(i)));
      stiff = (opt && opt.soft) ? o.stiffness : o.catchStiffness;
      damp  = (opt && opt.soft) ? o.damping   : o.catchDamping;
      wake();
    }

    function jump(i){                 // no physics — placement, not motion
      pos = Math.max(0, Math.min(maxPos(), i));
      vel = 0; target = null;
      emit();
    }

    surface.addEventListener('pointerdown', onDown);
    surface.addEventListener('pointermove', onMove);
    surface.addEventListener('pointerup', onUp);
    surface.addEventListener('pointercancel', onUp);
    surface.addEventListener('click', onClickCapture, true);
    surface.addEventListener('wheel', onWheel, {passive: false});

    return {
      goTo, jump,
      nearest: () => Math.max(0, Math.min(maxPos(), Math.round(pos))),
      pos: () => pos,
      isDragging: () => dragging,
      /* Re-emit without integrating: for when the consumer's layout changed
         (a card arrived, the viewport resized) and the transforms need
         recomputing against the same physical position. */
      resync: () => { pos = clampSoft(pos); emit(); },
      destroy(){
        sleep();
        surface.removeEventListener('pointerdown', onDown);
        surface.removeEventListener('pointermove', onMove);
        surface.removeEventListener('pointerup', onUp);
        surface.removeEventListener('pointercancel', onUp);
        surface.removeEventListener('click', onClickCapture, true);
        surface.removeEventListener('wheel', onWheel);
      },
    };
  }

  window.SSWheel = {create, DEFAULTS};
})();
