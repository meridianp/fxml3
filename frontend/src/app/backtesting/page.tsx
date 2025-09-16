/**
 * Backtesting Page
 *
 * Strategy backtesting and analysis interface
 */

import { BacktestingWorkbench } from '@/components/backtesting';

export default function BacktestingPage() {
  return <BacktestingWorkbench />;
}

export const metadata = {
  title: 'Backtesting Workbench - FXML4',
  description: 'Create and analyze trading strategy backtests with comprehensive performance metrics',
};
