import type { Workspace } from './workflow';

/** Small mathematical diagrams, rather than decorative interface icons. */
export default function WorkspaceVisual({ workspace }: { workspace: Workspace }) {
  return <svg viewBox="0 0 240 94" fill="none" aria-hidden="true">
    {workspace === 'model' && <g stroke="currentColor" strokeWidth="1.3"><rect x="78" y="14" width="84" height="64" rx="9"/><path d="M35 46h43m84 0h43M68 40l10 6-10 6m127-12 10 6-10 6M95 33h50M95 46h31M95 59h42"/><circle cx="45" cy="46" r="16" opacity=".25"/><circle cx="195" cy="46" r="16" opacity=".25"/></g>}
    {workspace === 'transform' && <g stroke="currentColor" strokeWidth="1.3"><path d="M27 66c23-59 41 19 63-37M27 77V17m0 60h65M109 46h22m-7-6 7 6-7 6"/><path d="M151 20h64v56h-64zM167 20v56m16-56v56m16-56v56m-48-42h64m-64 14h64m-64 14h64" opacity=".55"/><path d="m151 62 16-14 16 0 16-14 16-14"/></g>}
    {workspace === 'solve' && <g stroke="currentColor" strokeWidth="1.3"><path d="M72 17H60v60h12m35-60h12v60h-12M77 32h4m13 0h4M77 47h4m13 0h4M77 62h4m13 0h4M136 33h27m-27 12h27m-27 12h27M177 17h-5v60h5m17-60h5v60h-5"/><circle cx="185" cy="32" r="2"/><circle cx="185" cy="47" r="2"/><circle cx="185" cy="62" r="2"/></g>}
    {workspace === 'results' && <g stroke="currentColor" strokeWidth="1.3"><path d="M33 16v61h180M33 47h180M78 16v61m45-61v61m45-61v61" opacity=".2"/><path d="M33 65c27 0 30-39 58-39s31 32 60 18 34-22 62-22M33 36c34 0 33 33 65 33s45-35 65-21 33 11 50 11"/><circle cx="91" cy="26" r="3" fill="currentColor"/></g>}
  </svg>;
}
