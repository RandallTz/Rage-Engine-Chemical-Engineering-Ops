import {checklistMarkdown} from '../datos';

export function GET() {
  return new Response(checklistMarkdown(), {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Content-Disposition': 'attachment; filename="engine-checklist.md"',
    },
  });
}
