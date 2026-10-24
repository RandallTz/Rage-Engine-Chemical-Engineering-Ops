'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { swapCharts } from './chartLayout';

type Chart = { id: string; nombre: string };
type Drag = {
  id: string; pointerId: number; card: HTMLElement; x: number; y: number;
  startX: number; startY: number; scrollStart: number; scroller: HTMLElement;
  active: boolean; target: HTMLElement | null; frame: number; listeners: AbortController;
};
type Position = { left: number; top: number };

/** Pointer motion stays outside React rendering; only the final layout is persisted. */
export function useChartDrag<T extends Chart>(charts: T[], save: (charts: T[]) => boolean | void, enabled = true) {
  const gridRef = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag | null>(null);
  const pending = useRef<Map<string, Position> | null>(null);
  const animations = useRef<Animation[]>([]);
  const [announcement, setAnnouncement] = useState('');
  const layout = JSON.stringify(charts);
  const bindGrid = useCallback((element: HTMLDivElement | null) => { gridRef.current = element; }, []);

  const snapshot = useCallback(() => {
    return new Map(Array.from(gridRef.current?.querySelectorAll<HTMLElement>('[data-plot-id]') ?? [], element => [element.dataset.plotId!, element.getBoundingClientRect()]));
  }, []);
  const animateFrom = useCallback((positions: Map<string, Position>) => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animations.current.forEach(animation => animation.cancel());
    animations.current = [];
    gridRef.current?.querySelectorAll<HTMLElement>('[data-plot-id]').forEach(element => {
      const before = positions.get(element.dataset.plotId!);
      if (!before) return;
      const after = element.getBoundingClientRect();
      const x = before.left - after.left, y = before.top - after.top;
      if (Math.abs(x) + Math.abs(y) < 1) return;
      animations.current.push(element.animate([
        { transform: `translate3d(${x}px,${y}px,0)` }, { transform: 'translate3d(0,0,0)' },
      ], { duration: 320, easing: 'cubic-bezier(.2,.75,.25,1)' }));
    });
  }, []);
  const clearSession = useCallback(() => {
    const session = drag.current;
    if (!session) return;
    drag.current = null;
    session.listeners.abort(); cancelAnimationFrame(session.frame);
    session.target?.removeAttribute('data-drop-target');
    session.card.removeAttribute('data-dragging');
    session.card.style.removeProperty('--chart-drag-x');
    session.card.style.removeProperty('--chart-drag-y');
    gridRef.current?.removeAttribute('data-drag-active');
    if (session.card.hasPointerCapture(session.pointerId)) session.card.releasePointerCapture(session.pointerId);
  }, []);
  const cancel = useCallback(() => {
    const positions = snapshot(), active = drag.current?.active;
    clearSession();
    if (active) { animateFrom(positions); setAnnouncement('Chart move cancelled.'); }
  }, [snapshot, clearSession, animateFrom]);

  useLayoutEffect(() => {
    if (pending.current) { const positions = pending.current; pending.current = null; animateFrom(positions); }
  }, [layout, animateFrom]);
  useEffect(() => () => { clearSession(); animations.current.forEach(animation => animation.cancel()); }, [clearSession]);
  useEffect(() => { if (drag.current) cancel(); }, [layout, enabled, cancel]);

  function start(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || !event.isPrimary || drag.current) return;
    const element = event.target as Element;
    const handle = element.closest('[data-chart-handle]');
    if (element.closest('button,input,select,textarea,a,[role="slider"],[contenteditable="true"]') && !handle) return;
    // Touch users keep page scrolling over plots; the move handle owns touch dragging.
    if (event.pointerType === 'touch' && !handle) return;
    const card = element.closest<HTMLElement>('[data-plot-id]');
    if (!card || !gridRef.current?.contains(card)) return;
    animations.current.forEach(animation => animation.cancel());
    let scroller = card.parentElement;
    while (scroller && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowY)) scroller = scroller.parentElement;
    scroller ??= document.scrollingElement as HTMLElement;
    const session: Drag = { id: card.dataset.plotId!, pointerId: event.pointerId, card,
      x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY,
      scrollStart: scroller.scrollTop, scroller, active: false, target: null, frame: 0, listeners: new AbortController() };
    drag.current = session;
    if (handle) event.preventDefault();
    const signal = session.listeners.signal;

    function updateTarget() {
      const target = document.elementFromPoint(session.x, session.y)?.closest<HTMLElement>('[data-plot-id]') ?? null;
      const next = target && target !== card && gridRef.current?.contains(target) ? target : null;
      if (next !== session.target) {
        session.target?.removeAttribute('data-drop-target');
        session.target = next;
        next?.setAttribute('data-drop-target', 'true');
        if (next) setAnnouncement(`Release to swap with ${charts.find(chart => chart.id === next.dataset.plotId)?.nombre ?? 'this chart'}.`);
      }
    }
    function frame() {
      if (drag.current !== session || !session.active) return;
      const bounds = session.scroller.getBoundingClientRect();
      const top = Math.max(0, bounds.top), bottom = Math.min(innerHeight, bounds.bottom);
      const speed = session.y < top + 64 ? -Math.min(14, (top + 64 - session.y) / 4)
        : session.y > bottom - 64 ? Math.min(14, (session.y - bottom + 64) / 4) : 0;
      if (session.x >= bounds.left && session.x <= bounds.right && speed) session.scroller.scrollTop += speed;
      session.card.style.setProperty('--chart-drag-x', `${session.x - session.startX}px`);
      session.card.style.setProperty('--chart-drag-y', `${session.y - session.startY + session.scroller.scrollTop - session.scrollStart}px`);
      updateTarget();
      session.frame = requestAnimationFrame(frame);
    }
    window.addEventListener('pointermove', move => {
      if (move.pointerId !== session.pointerId) return;
      session.x = move.clientX; session.y = move.clientY;
      if (!session.active && Math.hypot(session.x - session.startX, session.y - session.startY) >= 6) {
        session.active = true;
        card.setPointerCapture(session.pointerId);
        card.setAttribute('data-dragging', 'true'); gridRef.current?.setAttribute('data-drag-active', 'true');
        setAnnouncement(`Moving ${charts.find(chart => chart.id === session.id)?.nombre ?? 'chart'}. Press Escape to cancel.`);
        frame();
      }
      if (session.active) move.preventDefault();
    }, { signal, passive: false });
    window.addEventListener('pointerup', up => {
      if (up.pointerId !== session.pointerId) return;
      session.x = up.clientX; session.y = up.clientY;
      if (session.active) updateTarget();
      const targetId = session.target?.dataset.plotId;
      const positions = snapshot();
      clearSession();
      if (session.active && targetId) {
        pending.current = positions;
        if (save(swapCharts(charts, session.id, targetId)) === false) {
          pending.current = null; animateFrom(positions); setAnnouncement('The chart order could not be saved.');
        } else setAnnouncement('Chart positions swapped and saved.');
      } else if (session.active) { animateFrom(positions); setAnnouncement('Chart returned to its original position.'); }
    }, { signal });
    window.addEventListener('pointercancel', cancel, { signal });
    card.addEventListener('lostpointercapture', cancel, { signal });
    window.addEventListener('blur', cancel, { signal });
    window.addEventListener('resize', cancel, { signal });
    window.addEventListener('keydown', key => { if (key.key === 'Escape') { key.preventDefault(); cancel(); } }, { signal });
  }

  function swap(source: string, target: string) {
    pending.current = snapshot();
    if (save(swapCharts(charts, source, target)) === false) {
      pending.current = null; setAnnouncement('The chart order could not be saved.');
    } else setAnnouncement('Chart positions swapped and saved.');
  }
  return { bindGrid, start, swap, announcement };
}
