const withPWA = require('next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    {
      urlPattern: /^https?.*$/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'offlineCache',
        expiration: {
          maxEntries: 200,
        },
      },
    },
    {
      urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'images-cache',
        expiration: {
          maxEntries: 100,
          maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
        },
      },
    },
    {
      urlPattern: /\.(?:js|css)$/,
      handler: 'StaleWhileRevalidate',
      options: {
        cacheName: 'static-cache',
        expiration: {
          maxEntries: 100,
          maxAgeSeconds: 24 * 60 * 60, // 24 hours
        },
      },
    },
    {
      urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
      handler: 'NetworkFirst',
      options: {
        cacheName: 'api-cache',
        expiration: {
          maxEntries: 50,
          maxAgeSeconds: 5 * 60, // 5 minutes
        },
        networkTimeoutSeconds: 10,
      },
    },
  ],
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Disable type checking during build for now
  typescript: {
    ignoreBuildErrors: true,
  },

  // Enable experimental features for better performance
  experimental: {
    esmExternals: true,
    serverComponentsExternalPackages: [],
    legacyBrowsers: false,
    optimizeCss: process.env.NODE_ENV === 'production',
  },

  // Configure for trading application requirements
  env: {
    NEXT_PUBLIC_APP_NAME: 'FXML4 Trading Platform',
    NEXT_PUBLIC_APP_VERSION: '1.0.0',
    BUNDLE_ANALYZE: process.env.ANALYZE,
  },

  // Compiler optimizations
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production' ? {
      exclude: ['error', 'warn'],
    } : false,
    reactRemoveProperties: process.env.NODE_ENV === 'production',
  },

  // API configuration
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: process.env.FXML4_API_URL ?
          `${process.env.FXML4_API_URL}/api/v1/:path*` :
          'http://localhost:8000/api/v1/:path*',
      },
      {
        source: '/api/:path*',
        destination: process.env.FXML4_API_URL ?
          `${process.env.FXML4_API_URL}/api/:path*` :
          'http://localhost:8000/api/:path*',
      },
    ];
  },

  // Headers for security and performance
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
      {
        source: '/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      {
        source: '/_next/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },

  // Images configuration for trading charts and logos
  images: {
    domains: ['localhost'],
    formats: ['image/webp', 'image/avif'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
  },

  // Output configuration
  output: process.env.NODE_ENV === 'production' ? 'standalone' : undefined,

  // Enable gzip compression
  compress: true,

  // Remove powered by header
  poweredByHeader: false,

  // Webpack configuration for optimal performance
  webpack: (config, { buildId, dev, isServer, defaultLoaders, webpack }) => {
    // Bundle analyzer configuration
    if (process.env.ANALYZE === 'true') {
      const { BundleAnalyzerPlugin } = require('webpack-bundle-analyzer');
      config.plugins.push(
        new BundleAnalyzerPlugin({
          analyzerMode: 'static',
          reportFilename: isServer
            ? '../analyze/server.html'
            : '../analyze/client.html',
          openAnalyzer: false,
        })
      );
    }

    // Optimize chunks and splitting
    config.optimization = {
      ...config.optimization,

      // Split chunks for better caching
      splitChunks: {
        chunks: 'all',
        minSize: 20000,
        maxSize: 244000,
        cacheGroups: {
          // Vendor chunks
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            priority: 10,
            chunks: 'all',
          },

          // React and React DOM
          react: {
            test: /[\\/]node_modules[\\/](react|react-dom)[\\/]/,
            name: 'react',
            priority: 20,
            chunks: 'all',
          },

          // Chart libraries
          charts: {
            test: /[\\/]node_modules[\\/](recharts|lightweight-charts)[\\/]/,
            name: 'charts',
            priority: 15,
            chunks: 'all',
          },

          // UI libraries
          ui: {
            test: /[\\/]node_modules[\\/](@headlessui|@heroicons|@radix-ui|framer-motion)[\\/]/,
            name: 'ui',
            priority: 15,
            chunks: 'all',
          },

          // Utilities
          utils: {
            test: /[\\/]node_modules[\\/](axios|date-fns|clsx|tailwind-merge)[\\/]/,
            name: 'utils',
            priority: 12,
            chunks: 'all',
          },

          // Common components
          common: {
            name: 'common',
            minChunks: 2,
            priority: 5,
            chunks: 'all',
            enforce: true,
          },
        },
      },

      // Module concatenation for better tree shaking
      concatenateModules: true,

      // Minimize in production
      minimize: !dev,
    };

    config.resolve.fallback = {
      fs: false,
      path: false,
      os: false,
    };

    // Tree shaking configuration
    config.resolve.alias = {
      ...config.resolve.alias,
      // Ensure tree shaking for lodash
      'lodash': 'lodash-es',
    };

    // Exclude heavy dependencies from server bundle
    if (isServer) {
      config.externals = [...config.externals, 'canvas'];
    }

    // Compression plugins for production
    if (!dev && !isServer) {
      const CompressionPlugin = require('compression-webpack-plugin');

      config.plugins.push(
        new CompressionPlugin({
          algorithm: 'gzip',
          test: /\.(js|css|html|svg)$/,
          threshold: 8192,
          minRatio: 0.8,
        })
      );
    }

    return config;
  },
};

module.exports = withPWA(nextConfig);
