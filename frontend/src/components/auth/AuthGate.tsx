import { GoogleLogin } from '@react-oauth/google';
import { Shield } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import Card from '../ui/Card';

interface AuthGateProps {
  children: React.ReactNode;
  message?: string;
}

/**
 * Wraps content that requires authentication.
 * Shows a sign-in prompt if the user is not logged in.
 */
export default function AuthGate({
  children,
  message = 'Sign in to generate AI-powered research reports',
}: AuthGateProps) {
  const { user, login, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-32">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (user) {
    return <>{children}</>;
  }

  return (
    <div className="flex items-center justify-center py-24 px-4">
      <Card className="max-w-md w-full text-center">
        <div className="flex justify-center mb-4">
          <div className="w-14 h-14 rounded-full bg-accent-light flex items-center justify-center">
            <Shield size={28} className="text-accent" />
          </div>
        </div>

        <h2 className="text-xl font-bold mb-2">Sign in Required</h2>
        <p className="text-muted text-sm mb-6">{message}</p>

        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={async (response) => {
              if (response.credential) {
                try {
                  await login(response.credential);
                } catch (err) {
                  console.error('Login failed:', err);
                }
              }
            }}
            onError={() => console.error('Google login error')}
            size="large"
            theme="outline"
            shape="pill"
            text="signin_with"
            width="300"
          />
        </div>

        <p className="text-xs text-muted mt-4">
          Free to use. We only need your Google account to track your report history.
        </p>
      </Card>
    </div>
  );
}
