/**
 * Register Page
 *
 * User registration page
 */

import { RegisterForm } from '@/components/auth';

export default function RegisterPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <RegisterForm />
      </div>
    </div>
  );
}

export const metadata = {
  title: 'Register - FXML4',
  description: 'Create your FXML4 trading account',
};
