/**
 * Theme Toggle Component
 *
 * Button component for switching between light, dark, and system themes
 */

'use client';

import React from 'react';
import { Button } from './button';
import { useTheme } from '@/components/providers';
import {
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon
} from '@heroicons/react/24/outline';

interface ThemeToggleProps {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'ghost' | 'outline';
  showLabel?: boolean;
  className?: string;
}

const themeIcons = {
  light: SunIcon,
  dark: MoonIcon,
  system: ComputerDesktopIcon,
};

const themeLabels = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
};

export default function ThemeToggle({
  size = 'md',
  variant = 'ghost',
  showLabel = false,
  className = ''
}: ThemeToggleProps) {
  const { theme, setTheme, toggleTheme } = useTheme();

  const Icon = themeIcons[theme];
  const label = themeLabels[theme];

  return (
    <Button
      data-testid="theme-toggle"
      onClick={toggleTheme}
      variant={variant}
      size={size}
      className={`gap-2 ${className}`}
      title={`Switch theme (currently ${label.toLowerCase()})`}
      aria-label={`Switch theme (currently ${label.toLowerCase()})`}
    >
      <Icon className="w-4 h-4" />
      {showLabel && <span className="hidden sm:inline">{label}</span>}
    </Button>
  );
}

// Dropdown version for settings pages
export function ThemeSelect({
  value,
  onChange,
  className = ""
}: {
  value?: string;
  onChange?: (value: string) => void;
  className?: string;
}) {
  const { theme, setTheme } = useTheme();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newTheme = e.target.value as 'light' | 'dark' | 'system';
    setTheme(newTheme);
    onChange?.(newTheme);
  };

  return (
    <select
      data-testid="theme-select"
      value={value || theme}
      onChange={handleChange}
      className={`w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 ${className}`}
    >
      <option value="dark">Dark</option>
      <option value="light">Light</option>
      <option value="system">System</option>
    </select>
  );
}
