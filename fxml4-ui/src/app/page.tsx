/**
 * Home Page
 *
 * Main landing page that redirects to dashboard
 */

import { redirect } from 'next/navigation';

export default function HomePage() {
  redirect('/dashboard');
}

export const metadata = {
  title: 'FXML4 Trading Platform',
  description: 'Professional forex trading platform with ML-powered signals and comprehensive analytics',
};
