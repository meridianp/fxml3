/**
 * Phase 7 - Enhanced Authentication Interface
 * 
 * Comprehensive authentication system that integrates with Phase 4
 * security framework including 2FA, audit logging, and role-based access.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  LockClosedIcon,
  ShieldCheckIcon,
  KeyIcon,
  UserIcon,
  EyeIcon,
  EyeSlashIcon,
  DevicePhoneMobileIcon,
  ComputerDesktopIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';

// Authentication Types
interface LoginCredentials {
  username: string;
  password: string;
  totpCode?: string;
  rememberDevice?: boolean;
}

interface UserProfile {
  id: string;
  username: string;
  email: string;
  fullName: string;
  role: 'admin' | 'trader' | 'compliance' | 'risk_manager' | 'viewer';
  permissions: string[];
  lastLogin: string;
  lastPasswordChange: string;
  twoFactorEnabled: boolean;
  accountLocked: boolean;
  failedLoginAttempts: number;
  sessionTimeout: number; // minutes
}

interface LoginSession {
  id: string;
  deviceType: 'desktop' | 'mobile' | 'tablet';
  browser: string;
  ipAddress: string;
  location: string;
  loginTime: string;
  lastActivity: string;
  isCurrentSession: boolean;
  riskScore: 'low' | 'medium' | 'high';
}

interface SecurityEvent {
  id: string;
  type: 'login' | 'logout' | 'failed_login' | 'password_change' | '2fa_setup' | 'permission_denied';
  description: string;
  timestamp: string;
  ipAddress: string;
  userAgent: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export default function EnhancedAuthInterface() {
  const [activeTab, setActiveTab] = useState('login');
  const [isLoading, setIsLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [show2FASetup, setShow2FASetup] = useState(false);
  
  // Form states
  const [loginForm, setLoginForm] = useState<LoginCredentials>({
    username: '',
    password: '',
    totpCode: '',
    rememberDevice: false
  });
  
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [activeSessions, setActiveSessions] = useState<LoginSession[]>([]);
  const [securityEvents, setSecurityEvents] = useState<SecurityEvent[]>([]);
  const [qrCodeUrl, setQrCodeUrl] = useState<string>('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);

  // Mock data for demonstration
  useEffect(() => {
    const mockUserProfile: UserProfile = {
      id: '1',
      username: 'john.trader',
      email: 'john@example.com',
      fullName: 'John Trader',
      role: 'trader',
      permissions: ['trade.execute', 'data.view', 'reports.generate'],
      lastLogin: new Date(Date.now() - 3600000).toISOString(),
      lastPasswordChange: new Date(Date.now() - 86400000 * 30).toISOString(),
      twoFactorEnabled: true,
      accountLocked: false,
      failedLoginAttempts: 0,
      sessionTimeout: 480 // 8 hours
    };

    const mockSessions: LoginSession[] = [
      {
        id: '1',
        deviceType: 'desktop',
        browser: 'Chrome 120.0',
        ipAddress: '192.168.1.100',
        location: 'New York, US',
        loginTime: new Date(Date.now() - 3600000).toISOString(),
        lastActivity: new Date(Date.now() - 300000).toISOString(),
        isCurrentSession: true,
        riskScore: 'low'
      },
      {
        id: '2',
        deviceType: 'mobile',
        browser: 'Safari 17.1',
        ipAddress: '192.168.1.101',
        location: 'New York, US',
        loginTime: new Date(Date.now() - 86400000).toISOString(),
        lastActivity: new Date(Date.now() - 7200000).toISOString(),
        isCurrentSession: false,
        riskScore: 'low'
      }
    ];

    const mockSecurityEvents: SecurityEvent[] = [
      {
        id: '1',
        type: 'login',
        description: 'Successful login from desktop browser',
        timestamp: new Date(Date.now() - 3600000).toISOString(),
        ipAddress: '192.168.1.100',
        userAgent: 'Chrome/120.0.0.0',
        severity: 'low'
      },
      {
        id: '2',
        type: 'failed_login',
        description: 'Failed login attempt - incorrect password',
        timestamp: new Date(Date.now() - 86400000).toISOString(),
        ipAddress: '203.0.113.45',
        userAgent: 'Firefox/119.0',
        severity: 'medium'
      },
      {
        id: '3',
        type: '2fa_setup',
        description: 'Two-factor authentication enabled',
        timestamp: new Date(Date.now() - 86400000 * 7).toISOString(),
        ipAddress: '192.168.1.100',
        userAgent: 'Chrome/119.0.0.0',
        severity: 'low'
      }
    ];

    // Simulate authentication check
    const token = localStorage.getItem('auth_token');
    if (token) {
      setIsAuthenticated(true);
      setUserProfile(mockUserProfile);
      setActiveSessions(mockSessions);
      setSecurityEvents(mockSecurityEvents);
      setActiveTab('profile');
    }
  }, []);

  // Handle login
  const handleLogin = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Mock authentication logic
      if (loginForm.username === 'demo' && loginForm.password === 'password') {
        if (userProfile?.twoFactorEnabled && !loginForm.totpCode) {
          throw new Error('2FA code required');
        }
        
        localStorage.setItem('auth_token', 'mock_jwt_token');
        setIsAuthenticated(true);
        setActiveTab('profile');
      } else {
        throw new Error('Invalid credentials');
      }
      
    } catch (error) {
      console.error('Login failed:', error);
      alert(error instanceof Error ? error.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  }, [loginForm, userProfile]);

  // Handle logout
  const handleLogout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
    setUserProfile(null);
    setActiveTab('login');
    setLoginForm({
      username: '',
      password: '',
      totpCode: '',
      rememberDevice: false
    });
  }, []);

  // Handle session termination
  const terminateSession = useCallback((sessionId: string) => {
    setActiveSessions(prev => prev.filter(session => session.id !== sessionId));
    // In real app, would call API to terminate session
  }, []);

  // Handle 2FA setup
  const setup2FA = useCallback(async () => {
    setIsLoading(true);
    try {
      // Simulate API call to get QR code
      await new Promise(resolve => setTimeout(resolve, 1000));
      setQrCodeUrl('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='); // Placeholder
      setBackupCodes(['1234-5678', '2345-6789', '3456-7890', '4567-8901', '5678-9012']);
      setShow2FASetup(true);
    } catch (error) {
      console.error('2FA setup failed:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Get role badge color
  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-red-100 text-red-800';
      case 'trader': return 'bg-blue-100 text-blue-800';
      case 'compliance': return 'bg-purple-100 text-purple-800';
      case 'risk_manager': return 'bg-orange-100 text-orange-800';
      case 'viewer': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Get device icon
  const getDeviceIcon = (deviceType: string) => {
    switch (deviceType) {
      case 'mobile': return <DevicePhoneMobileIcon className="w-4 h-4" />;
      case 'tablet': return <DevicePhoneMobileIcon className="w-4 h-4" />;
      default: return <ComputerDesktopIcon className="w-4 h-4" />;
    }
  };

  // Get severity color
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-50 border-red-200';
      case 'high': return 'text-orange-600 bg-orange-50 border-orange-200';
      case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'low': return 'text-blue-600 bg-blue-50 border-blue-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="w-full max-w-4xl">
        <Card className="shadow-2xl">
          <CardHeader className="bg-gradient-to-r from-blue-600 to-purple-600 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <ShieldCheckIcon className="w-8 h-8" />
                <div>
                  <CardTitle className="text-xl font-bold">FXML4 Security Center</CardTitle>
                  <p className="text-sm opacity-90">
                    Enterprise-grade authentication and access management
                  </p>
                </div>
              </div>
              {isAuthenticated && (
                <Button 
                  variant="outline" 
                  onClick={handleLogout}
                  className="border-white text-white hover:bg-white hover:text-blue-600"
                >
                  <XMarkIcon className="w-4 h-4 mr-2" />
                  Logout
                </Button>
              )}
            </div>
          </CardHeader>

          <CardContent className="p-0">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-4 rounded-none border-b">
                <TabsTrigger value="login" disabled={isAuthenticated}>Login</TabsTrigger>
                <TabsTrigger value="profile" disabled={!isAuthenticated}>Profile</TabsTrigger>
                <TabsTrigger value="sessions" disabled={!isAuthenticated}>Sessions</TabsTrigger>
                <TabsTrigger value="security" disabled={!isAuthenticated}>Security</TabsTrigger>
              </TabsList>

              <TabsContent value="login" className="p-6 space-y-6">
                <div className="text-center mb-8">
                  <h2 className="text-2xl font-bold text-gray-900">Sign In</h2>
                  <p className="text-gray-600 mt-2">Access your FXML4 trading platform</p>
                </div>

                <form onSubmit={handleLogin} className="space-y-4 max-w-md mx-auto">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Username
                    </label>
                    <div className="relative">
                      <UserIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="text"
                        required
                        value={loginForm.username}
                        onChange={(e) => setLoginForm(prev => ({ ...prev, username: e.target.value }))}
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Enter username"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Password
                    </label>
                    <div className="relative">
                      <LockClosedIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        required
                        value={loginForm.password}
                        onChange={(e) => setLoginForm(prev => ({ ...prev, password: e.target.value }))}
                        className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Enter password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? <EyeSlashIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>

                  {userProfile?.twoFactorEnabled && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        2FA Code
                      </label>
                      <div className="relative">
                        <KeyIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                        <input
                          type="text"
                          value={loginForm.totpCode}
                          onChange={(e) => setLoginForm(prev => ({ ...prev, totpCode: e.target.value }))}
                          className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                          placeholder="Enter 6-digit code"
                          maxLength={6}
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="rememberDevice"
                      checked={loginForm.rememberDevice}
                      onChange={(e) => setLoginForm(prev => ({ ...prev, rememberDevice: e.target.checked }))}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label htmlFor="rememberDevice" className="ml-2 block text-sm text-gray-700">
                      Remember this device for 30 days
                    </label>
                  </div>

                  <Button 
                    type="submit" 
                    disabled={isLoading}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-md font-medium"
                  >
                    {isLoading ? 'Signing In...' : 'Sign In'}
                  </Button>

                  <div className="text-center text-sm text-gray-600">
                    Demo credentials: username = "demo", password = "password"
                  </div>
                </form>
              </TabsContent>

              <TabsContent value="profile" className="p-6 space-y-6">
                {userProfile && (
                  <>
                    <div className="flex items-center justify-between">
                      <h3 className="text-xl font-semibold">User Profile</h3>
                      <Badge className={`${getRoleBadgeColor(userProfile.role)} border`}>
                        {userProfile.role.replace('_', ' ').toUpperCase()}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div>
                          <label className="text-sm font-medium text-gray-600">Full Name</label>
                          <p className="text-lg font-semibold text-gray-900">{userProfile.fullName}</p>
                        </div>
                        <div>
                          <label className="text-sm font-medium text-gray-600">Username</label>
                          <p className="text-lg font-semibold text-gray-900">{userProfile.username}</p>
                        </div>
                        <div>
                          <label className="text-sm font-medium text-gray-600">Email</label>
                          <p className="text-lg font-semibold text-gray-900">{userProfile.email}</p>
                        </div>
                        <div>
                          <label className="text-sm font-medium text-gray-600">Last Login</label>
                          <p className="text-lg font-semibold text-gray-900">
                            {format(new Date(userProfile.lastLogin), 'PPpp')}
                          </p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <label className="text-sm font-medium text-gray-600">Two-Factor Authentication</label>
                          <div className="flex items-center space-x-2 mt-1">
                            {userProfile.twoFactorEnabled ? (
                              <CheckCircleIcon className="w-5 h-5 text-green-500" />
                            ) : (
                              <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />
                            )}
                            <span className={`font-semibold ${userProfile.twoFactorEnabled ? 'text-green-600' : 'text-red-600'}`}>
                              {userProfile.twoFactorEnabled ? 'Enabled' : 'Disabled'}
                            </span>
                          </div>
                          {!userProfile.twoFactorEnabled && (
                            <Button 
                              onClick={setup2FA} 
                              disabled={isLoading}
                              className="mt-2 bg-blue-600 hover:bg-blue-700 text-white"
                            >
                              Enable 2FA
                            </Button>
                          )}
                        </div>

                        <div>
                          <label className="text-sm font-medium text-gray-600">Session Timeout</label>
                          <p className="text-lg font-semibold text-gray-900">
                            {Math.floor(userProfile.sessionTimeout / 60)} hours {userProfile.sessionTimeout % 60} minutes
                          </p>
                        </div>

                        <div>
                          <label className="text-sm font-medium text-gray-600">Account Status</label>
                          <div className="flex items-center space-x-2 mt-1">
                            {userProfile.accountLocked ? (
                              <XMarkIcon className="w-5 h-5 text-red-500" />
                            ) : (
                              <CheckCircleIcon className="w-5 h-5 text-green-500" />
                            )}
                            <span className={`font-semibold ${userProfile.accountLocked ? 'text-red-600' : 'text-green-600'}`}>
                              {userProfile.accountLocked ? 'Locked' : 'Active'}
                            </span>
                          </div>
                        </div>

                        <div>
                          <label className="text-sm font-medium text-gray-600">Permissions</label>
                          <div className="flex flex-wrap gap-2 mt-2">
                            {userProfile.permissions.map((permission) => (
                              <Badge key={permission} variant="outline" className="text-xs">
                                {permission}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </TabsContent>

              <TabsContent value="sessions" className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-semibold">Active Sessions</h3>
                  <Badge variant="outline">
                    {activeSessions.length} active session{activeSessions.length !== 1 ? 's' : ''}
                  </Badge>
                </div>

                <div className="space-y-4">
                  {activeSessions.map((session) => (
                    <Card key={session.id} className={`${session.isCurrentSession ? 'ring-2 ring-blue-500' : ''}`}>
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start space-x-4">
                            <div className="flex-shrink-0">
                              {getDeviceIcon(session.deviceType)}
                            </div>
                            <div>
                              <div className="flex items-center space-x-2">
                                <h4 className="font-medium text-gray-900">{session.browser}</h4>
                                {session.isCurrentSession && (
                                  <Badge className="bg-green-100 text-green-800">Current</Badge>
                                )}
                                <Badge variant="outline" className={
                                  session.riskScore === 'high' ? 'text-red-600 border-red-300' :
                                  session.riskScore === 'medium' ? 'text-yellow-600 border-yellow-300' :
                                  'text-green-600 border-green-300'
                                }>
                                  {session.riskScore} risk
                                </Badge>
                              </div>
                              <p className="text-sm text-gray-600 mt-1">
                                {session.location} • {session.ipAddress}
                              </p>
                              <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                                <span>Login: {format(new Date(session.loginTime), 'PPp')}</span>
                                <span>Last activity: {format(new Date(session.lastActivity), 'PPp')}</span>
                              </div>
                            </div>
                          </div>
                          {!session.isCurrentSession && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => terminateSession(session.id)}
                              className="text-red-600 border-red-300 hover:bg-red-50"
                            >
                              Terminate
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="security" className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-semibold">Security Events</h3>
                  <Button variant="outline" size="sm">
                    <ClockIcon className="w-4 h-4 mr-2" />
                    View All
                  </Button>
                </div>

                <div className="space-y-4">
                  {securityEvents.map((event) => (
                    <motion.div
                      key={event.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`p-4 rounded-lg border ${getSeverityColor(event.severity)}`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center space-x-2 mb-2">
                            <Badge variant="outline" className="text-xs">
                              {event.type.replace('_', ' ').toUpperCase()}
                            </Badge>
                            <Badge variant="outline" className={`text-xs ${getSeverityColor(event.severity)}`}>
                              {event.severity}
                            </Badge>
                          </div>
                          <p className="font-medium text-gray-900 mb-1">{event.description}</p>
                          <div className="text-sm text-gray-600 space-y-1">
                            <p>Time: {format(new Date(event.timestamp), 'PPpp')}</p>
                            <p>IP: {event.ipAddress}</p>
                            <p>User Agent: {event.userAgent}</p>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* 2FA Setup Modal */}
        <AnimatePresence>
          {show2FASetup && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="bg-white rounded-lg p-6 max-w-md w-full space-y-4"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Set up Two-Factor Authentication</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShow2FASetup(false)}
                  >
                    <XMarkIcon className="w-4 h-4" />
                  </Button>
                </div>
                
                <div className="text-center">
                  <div className="mb-4">
                    <img 
                      src={qrCodeUrl} 
                      alt="2FA QR Code" 
                      className="w-48 h-48 mx-auto bg-gray-100 rounded-lg"
                    />
                  </div>
                  <p className="text-sm text-gray-600 mb-4">
                    Scan this QR code with your authenticator app, then enter the 6-digit code to confirm setup.
                  </p>
                  
                  <div className="space-y-4">
                    <input
                      type="text"
                      placeholder="Enter 6-digit code"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                      maxLength={6}
                    />
                    
                    <div className="bg-yellow-50 p-3 rounded-md">
                      <p className="text-sm font-medium text-yellow-800 mb-2">Backup Codes</p>
                      <p className="text-xs text-yellow-700 mb-2">
                        Save these codes in a secure place. You can use them to access your account if you lose your phone.
                      </p>
                      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                        {backupCodes.map((code, index) => (
                          <div key={index} className="bg-white p-1 rounded border">
                            {code}
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    <Button className="w-full bg-blue-600 hover:bg-blue-700">
                      Complete Setup
                    </Button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}