/**
 * Login Page
 *
 * User authentication login page
 */

import { LoginForm } from '@/components/auth';

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <LoginForm />
      </div>
    </div>
  );
}

export const metadata = {
  title: 'Login - FXML4',
  description: 'Sign in to your FXML4 trading account',
};
