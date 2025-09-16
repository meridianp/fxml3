/**
 * Profile Page
 *
 * User profile and account management
 */

import { Button } from '@/components/ui/button';
import {
  UserCircleIcon,
  CameraIcon,
  ChartBarIcon,
  CurrencyDollarIcon,
  CalendarDaysIcon,
  TrophyIcon
} from '@heroicons/react/24/outline';

const profileStats = [
  { label: 'Total Trades', value: '1,247', icon: CurrencyDollarIcon, color: 'text-blue-400' },
  { label: 'Win Rate', value: '64.5%', icon: TrophyIcon, color: 'text-green-400' },
  { label: 'Total Return', value: '+23.8%', icon: ChartBarIcon, color: 'text-purple-400' },
  { label: 'Days Active', value: '183', icon: CalendarDaysIcon, color: 'text-orange-400' }
];

const recentActivity = [
  { action: 'Deployed ML Model', target: 'EURUSD Neural Network', time: '2 hours ago', type: 'model' },
  { action: 'Completed Backtest', target: 'MA Crossover Strategy', time: '4 hours ago', type: 'backtest' },
  { action: 'Closed Position', target: 'GBPUSD LONG +$127', time: '6 hours ago', type: 'trade' },
  { action: 'Updated Settings', target: 'Risk Management', time: '1 day ago', type: 'settings' },
  { action: 'Created Model', target: 'USDJPY LSTM', time: '2 days ago', type: 'model' }
];

const getActivityIcon = (type: string) => {
  switch (type) {
    case 'model': return '🧠';
    case 'backtest': return '📊';
    case 'trade': return '💰';
    case 'settings': return '⚙️';
    default: return '📝';
  }
};

export default function ProfilePage() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Profile</h1>
        <p className="text-gray-400">Manage your account and view trading statistics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Profile Info */}
        <div className="lg:col-span-1">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <div className="text-center mb-6">
              <div className="relative inline-block">
                <div className="w-24 h-24 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
                  JD
                </div>
                <button className="absolute bottom-0 right-0 w-8 h-8 bg-gray-700 hover:bg-gray-600 rounded-full flex items-center justify-center transition-colors">
                  <CameraIcon className="w-4 h-4 text-white" />
                </button>
              </div>
              <h2 className="text-xl font-semibold text-white mt-4">John Doe</h2>
              <p className="text-gray-400">Pro Trader</p>
              <div className="flex items-center justify-center gap-2 mt-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-green-400 text-sm">Online</span>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-gray-400">Email</span>
                <span className="text-white">john.doe@example.com</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Joined</span>
                <span className="text-white">Jan 15, 2024</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Experience</span>
                <span className="text-white">Advanced</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Account Type</span>
                <span className="text-purple-400">Premium</span>
              </div>
            </div>

            <Button className="w-full mt-6">
              Edit Profile
            </Button>
          </div>
        </div>

        {/* Stats and Activity */}
        <div className="lg:col-span-2 space-y-8">
          {/* Trading Statistics */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Trading Statistics</h3>
            <div className="grid grid-cols-2 gap-4">
              {profileStats.map((stat) => (
                <div key={stat.label} className="bg-gray-800/50 rounded-lg p-4">
                  <div className="flex items-center gap-3 mb-2">
                    <stat.icon className={`w-5 h-5 ${stat.color}`} />
                    <span className="text-gray-400 text-sm">{stat.label}</span>
                  </div>
                  <div className="text-2xl font-bold text-white">{stat.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Recent Activity</h3>
            <div className="space-y-3">
              {recentActivity.map((activity, index) => (
                <div key={index} className="flex items-center gap-4 p-3 bg-gray-800/30 rounded-lg">
                  <div className="text-xl">{getActivityIcon(activity.type)}</div>
                  <div className="flex-1">
                    <div className="text-white font-medium">
                      {activity.action} <span className="text-blue-400">{activity.target}</span>
                    </div>
                    <div className="text-gray-400 text-sm">{activity.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Account Settings Quick Actions */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Quick Actions</h3>
            <div className="grid grid-cols-2 gap-4">
              <Button variant="outline" className="h-12">
                Change Password
              </Button>
              <Button variant="outline" className="h-12">
                Download Data
              </Button>
              <Button variant="outline" className="h-12">
                API Settings
              </Button>
              <Button variant="outline" className="h-12">
                Notification Preferences
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export const metadata = {
  title: 'Profile - FXML4',
  description: 'User profile and account management for FXML4 trading platform',
};
