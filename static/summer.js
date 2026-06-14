/* Summer the pomeranian — pixel-art mascot */
(function () {
  // Frame layout in summer.png (64px × 64px per frame, 15 frames, rendered at 64px)
  const W = 64, H = 64, SCALE = 1;
  const PX = W * SCALE;   // 64
  const FRAMES = {
    walk:    [0, 1, 2, 3],
    idle:    [4, 5],
    sit:     [6, 7],
    sleep:   [8, 9],
    jump:    [10, 11, 12],
    bark:    [13, 14],
  };

  const STATES = ['idle', 'walk', 'sit', 'sleep', 'bark'];
  const WEIGHTS = { idle: 30, walk: 35, sit: 15, sleep: 15, bark: 5 };

  let el, bubble, x = 40, dir = 1, state = 'idle', frame = 0;
  let frameTimer = null, stateTimer = null, rafId = null;
  let targetX = 40, walking = false;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function setFrame(f) {
    const bgX = -(f * W * SCALE);
    el.style.backgroundPositionX = bgX + 'px';
  }

  function startFrameAnim(framelist, fps = 8) {
    clearInterval(frameTimer);
    let fi = 0;
    setFrame(framelist[fi]);
    frameTimer = setInterval(() => {
      fi = (fi + 1) % framelist.length;
      setFrame(framelist[fi]);
    }, 1000 / fps);
  }

  function setState(s) {
    state = s;
    walking = false;
    clearInterval(frameTimer);
    switch (s) {
      case 'idle':  startFrameAnim(FRAMES.idle,  3); break;
      case 'walk':  walkToRandom(); break;
      case 'sit':   startFrameAnim(FRAMES.sit,   2); break;
      case 'sleep': startFrameAnim(FRAMES.sleep, 1); break;
      case 'bark':  startFrameAnim(FRAMES.bark,  8);
        setTimeout(() => setState('idle'), 1200); break;
      case 'jump':
        startFrameAnim(FRAMES.jump, 10);
        showBubble('♥');
        setTimeout(() => setState('idle'), 1000);
        break;
    }
    scheduleNext();
  }

  function pickState() {
    const total = Object.values(WEIGHTS).reduce((a, b) => a + b, 0);
    let r = Math.random() * total;
    for (const [s, w] of Object.entries(WEIGHTS)) {
      r -= w;
      if (r <= 0) return s;
    }
    return 'idle';
  }

  function scheduleNext() {
    clearTimeout(stateTimer);
    if (['jump', 'bark'].includes(state)) return;
    const delay = 3000 + Math.random() * 9000;
    stateTimer = setTimeout(() => setState(pickState()), delay);
  }

  function walkToRandom() {
    const margin = 60;
    const maxX = window.innerWidth - PX - margin;
    targetX = margin + Math.random() * Math.max(0, maxX - margin);
    dir = targetX > x ? 1 : -1;
    el.style.transform = `scaleX(${dir}) translateX(0px)`;
    walking = true;
    startFrameAnim(FRAMES.walk, 8);
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(walkStep);
  }

  function walkStep() {
    if (!walking) return;
    const speed = 1.2;
    x += dir * speed;
    el.style.left = x + 'px';
    el.style.transform = `scaleX(${dir})`;
    const done = dir > 0 ? x >= targetX : x <= targetX;
    if (done) {
      walking = false;
      setState('idle');
    } else {
      rafId = requestAnimationFrame(walkStep);
    }
  }

  function showBubble(text) {
    bubble.textContent = text;
    bubble.style.left = (x + PX / 2 - 12) + 'px';
    bubble.style.display = 'block';
    bubble.style.animation = 'none';
    void bubble.offsetHeight;
    bubble.style.animation = 'bubble-pop 1.8s ease forwards';
    setTimeout(() => { bubble.style.display = 'none'; }, 1800);
  }

  function init() {
    const zone = document.getElementById('summer-zone');
    if (!zone) return;
    el     = document.getElementById('summer');
    bubble = document.getElementById('summer-bubble');
    if (!el) return;

    zone.style.display = 'block';
    el.style.backgroundImage = 'url(static/summer.png)';
    el.style.backgroundSize  = `${W * SCALE * 15}px ${H * SCALE}px`;
    el.style.width  = PX + 'px';
    el.style.height = PX + 'px';
    el.style.backgroundRepeat = 'no-repeat';
    el.style.left = x + 'px';

    el.addEventListener('click', () => {
      showBubble('♥');
      if (state !== 'jump') setState('bark');
    });

    if (reduced) {
      startFrameAnim(FRAMES.sit, 1);
      return;
    }

    setState('idle');
  }

  function hide() {
    const zone = document.getElementById('summer-zone');
    if (zone) zone.style.display = 'none';
    clearInterval(frameTimer);
    clearTimeout(stateTimer);
    if (rafId) cancelAnimationFrame(rafId);
  }

  function excite() {
    if (!el) return;
    setState('jump');
  }

  window.summer = { init, hide, excite };
})();
