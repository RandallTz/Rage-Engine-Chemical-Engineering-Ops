import type { Metadata } from 'next';
import MateriaFundamental from './MateriaFundamental';

export const metadata: Metadata = {
  title: 'Balance de materia · Motor',
};

export default function MotorPage() {
  return <MateriaFundamental />;
}
