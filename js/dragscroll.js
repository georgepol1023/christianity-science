/* A drag bar under a horizontal chip row (the broadcast seasons, the newspaper-column years), so a mouse can
 * slide the row right by dragging, instead of only swiping or shift-scrolling. Added only on desktop (a fine
 * pointer) and shown only while the chips are wider than the row; touch devices swipe, so they never get it.
 * Styling: .seasonscroll / .seasonscroll__thumb in css/site.css. Used by js/app.js and js/page.js. */
"use strict";
window.dragScroll = function (bar) {
  if (!bar || !window.matchMedia || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  var track = document.createElement("div");
  track.className = "seasonscroll";
  track.setAttribute("aria-hidden", "true");
  var thumb = document.createElement("div");
  thumb.className = "seasonscroll__thumb";
  track.appendChild(thumb);
  bar.insertAdjacentElement("afterend", track);

  var maxScroll = function () { return bar.scrollWidth - bar.clientWidth; };
  var sync = function () {
    var max = maxScroll();
    track.classList.toggle("is-on", max > 1);
    if (max <= 1) return;
    var tw = track.clientWidth, thumbW = Math.max(40, Math.round(tw * bar.clientWidth / bar.scrollWidth));
    thumb.style.width = thumbW + "px";
    thumb.style.transform = "translateX(" + (bar.scrollLeft / max) * (tw - thumbW) + "px)";
  };
  var drag = null;
  thumb.addEventListener("pointerdown", function (e) {
    drag = { x: e.clientX, left: bar.scrollLeft }; thumb.setPointerCapture(e.pointerId);
    track.classList.add("is-drag"); e.preventDefault();
  });
  thumb.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var travel = track.clientWidth - thumb.offsetWidth;
    if (travel > 0) bar.scrollLeft = drag.left + (e.clientX - drag.x) / travel * maxScroll();
  });
  var endDrag = function () { drag = null; track.classList.remove("is-drag"); };
  thumb.addEventListener("pointerup", endDrag);
  thumb.addEventListener("pointercancel", endDrag);
  track.addEventListener("pointerdown", function (e) {            // click the track to jump there
    if (e.target === thumb) return;
    var travel = track.clientWidth - thumb.offsetWidth;
    if (travel <= 0) return;
    var pos = e.clientX - track.getBoundingClientRect().left - thumb.offsetWidth / 2;
    bar.scrollLeft = Math.max(0, Math.min(1, pos / travel)) * maxScroll();
  });
  bar.addEventListener("scroll", sync, { passive: true });
  window.addEventListener("resize", sync);
  sync();
  setTimeout(sync, 0);                                            // again once fonts have settled the widths
};
