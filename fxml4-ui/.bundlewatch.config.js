/**
 * Bundle Watch Configuration
 *
 * Configuration for monitoring bundle size changes and preventing size regressions
 */

module.exports = {
  files: [
    {
      path: '.next/static/js/*.js',
      maxSize: '250kb',
      compression: 'gzip'
    },
    {
      path: '.next/static/css/*.css',
      maxSize: '50kb',
      compression: 'gzip'
    },
    {
      path: '.next/static/chunks/pages/*.js',
      maxSize: '150kb',
      compression: 'gzip'
    },
    {
      path: '.next/static/chunks/framework*.js',
      maxSize: '120kb',
      compression: 'gzip'
    },
    {
      path: '.next/static/chunks/main*.js',
      maxSize: '100kb',
      compression: 'gzip'
    },
    {
      path: '.next/static/chunks/webpack*.js',
      maxSize: '5kb',
      compression: 'gzip'
    }
  ],
  ci: {
    trackBranches: ['main', 'develop'],
    repoBranchBase: 'main'
  },
  defaultCompression: 'gzip',
  normalizeFilenames: /^.+?\/([^/]+\.(js|css))$/
};
