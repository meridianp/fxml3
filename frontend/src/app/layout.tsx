/**
 * Root Layout
 *
 * Main application layout with global providers and styles
 */

import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import { AppLayout } from '@/components/layout';
import { ThemeProvider } from '@/components/providers';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter'
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  userScalable: false,
  themeColor: '#1f2937'
};

export const metadata: Metadata = {
  title: 'FXML4 Trading Platform',
  description: 'Professional forex trading platform with ML-powered signals and comprehensive analytics',
  keywords: ['forex', 'trading', 'machine learning', 'backtesting', 'signals', 'analytics'],
  authors: [{ name: 'FXML4 Team' }],
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'FXML4 Trading',
    startupImage: [
      {
        url: '/images/startup/iphone5.png',
        media: '(device-width: 320px) and (device-height: 568px) and (-webkit-device-pixel-ratio: 2)'
      },
      {
        url: '/images/startup/iphone6.png',
        media: '(device-width: 375px) and (device-height: 667px) and (-webkit-device-pixel-ratio: 2)'
      },
      {
        url: '/images/startup/iphoneplus.png',
        media: '(device-width: 621px) and (device-height: 1104px) and (-webkit-device-pixel-ratio: 3)'
      },
      {
        url: '/images/startup/iphonex.png',
        media: '(device-width: 375px) and (device-height: 812px) and (-webkit-device-pixel-ratio: 3)'
      },
      {
        url: '/images/startup/ipadpro1.png',
        media: '(device-width: 834px) and (device-height: 1112px) and (-webkit-device-pixel-ratio: 2)'
      },
      {
        url: '/images/startup/ipadpro3.png',
        media: '(device-width: 834px) and (device-height: 1194px) and (-webkit-device-pixel-ratio: 2)'
      },
      {
        url: '/images/startup/ipadpro2.png',
        media: '(device-width: 1024px) and (device-height: 1366px) and (-webkit-device-pixel-ratio: 2)'
      }
    ]
  },
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/images/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/images/icons/icon-512.png', sizes: '512x512', type: 'image/png' }
    ],
    apple: [
      { url: '/images/icons/apple-icon-180.png', sizes: '180x180', type: 'image/png' }
    ]
  },
  openGraph: {
    title: 'FXML4 Trading Platform',
    description: 'Professional forex trading platform with ML-powered signals',
    type: 'website',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'FXML4 Trading Platform',
    description: 'Professional forex trading platform with ML-powered signals',
  },
  robots: {
    index: false, // Don't index trading platform
    follow: false,
  },
  other: {
    'mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-status-bar-style': 'black-translucent',
    'msapplication-TileColor': '#1f2937',
    'msapplication-config': '/browserconfig.xml',
    'format-detection': 'telephone=no',
  }
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} dark`} suppressHydrationWarning>
      <head>
        <meta name="color-scheme" content="dark light" />
      </head>
      <body className={`${inter.className} antialiased bg-gray-950 dark:bg-gray-950 bg-white dark:text-white text-gray-900 transition-colors`}>
        <ThemeProvider defaultTheme="dark">
          <AppLayout>
            {children}
          </AppLayout>
        </ThemeProvider>
      </body>
    </html>
  );
}
