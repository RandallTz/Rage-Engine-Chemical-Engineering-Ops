import {documentoChecklist} from '../datos';

export function GET() {
  return new Response(documentoChecklist(), {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Content-Disposition': 'attachment; filename="CHECKLIST_MOTOR.md"',
    },
  });
}
