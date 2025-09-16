/**
 * FXML4 Stryker Mutation Testing Configuration
 * Configures Stryker for comprehensive mutation testing of TypeScript/JavaScript code
 */

const path = require('path');

/**
 * Stryker configuration for FXML4 frontend components
 * @type {import('@stryker-mutator/api/core').PartialStrykerOptions}
 */
const config = {
  packageManager: 'npm',
  reporters: ['html', 'clear-text', 'progress', 'json'],
  testRunner: 'jest',
  testFramework: 'jest',
  coverageAnalysis: 'perTest',

  // Mutation configuration
  mutate: [
    'frontend/src/**/*.ts',
    'frontend/src/**/*.tsx',
    '!frontend/src/**/*.test.ts',
    '!frontend/src/**/*.test.tsx',
    '!frontend/src/**/*.spec.ts',
    '!frontend/src/**/*.spec.tsx',
    '!frontend/src/**/*.d.ts',
    '!frontend/src/**/__tests__/**',
    '!frontend/src/**/test/**',
    '!frontend/src/tests/**',
    '!frontend/src/setupTests.ts',
    '!frontend/src/reportWebVitals.ts'
  ],

  // Test file patterns
  testMatch: [
    'frontend/src/**/*.test.ts',
    'frontend/src/**/*.test.tsx',
    'frontend/src/**/*.spec.ts',
    'frontend/src/**/*.spec.tsx'
  ],

  // Mutation operators - comprehensive set for financial applications
  mutator: {
    plugins: [
      '@stryker-mutator/typescript-checker',
      '@stryker-mutator/jest-runner'
    ],
    excludedMutations: [
      // Exclude mutations that are generally noisy or not useful
      'StringLiteral', // Often causes false positives in UI text
      'RegexLiteral',  // Regex mutations are often complex to validate
    ]
  },

  // TypeScript configuration
  tsconfigFile: 'frontend/tsconfig.json',

  // Jest configuration
  jest: {
    projectType: 'custom',
    configFile: 'frontend/jest.config.js',
    enableFindRelatedTests: true
  },

  // Timeout configuration
  timeoutMS: 300000, // 5 minutes for full test suite
  timeoutFactor: 1.5,

  // Thresholds for mutation score
  thresholds: {
    high: 90,    // Target score for financial applications
    low: 80,     // Minimum acceptable score
    break: 70    // Build-breaking threshold
  },

  // Concurrency configuration
  concurrency: 4,
  maxConcurrentTestRunners: 4,

  // File patterns to ignore
  ignorePatterns: [
    '**/node_modules/**',
    '**/dist/**',
    '**/build/**',
    '**/.next/**',
    '**/coverage/**',
    '**/reports/**',
    '**/__tests__/**',
    '**/test/**',
    '**/tests/**'
  ],

  // Plugin configuration
  plugins: [
    '@stryker-mutator/core',
    '@stryker-mutator/jest-runner',
    '@stryker-mutator/typescript-checker'
  ],

  // Checker configuration
  checkers: ['typescript'],
  typescriptChecker: {
    prioritizePerformanceOverAccuracy: false
  },

  // HTML reporter configuration
  htmlReporter: {
    baseDir: '.claude-tdd/mutation/reports/frontend',
    fileName: 'mutation-report.html'
  },

  // JSON reporter configuration
  jsonReporter: {
    fileName: '.claude-tdd/mutation/reports/frontend/mutation-report.json'
  },

  // Clear text reporter configuration
  clearTextReporter: {
    allowColor: true,
    allowEmojis: true,
    logTests: false,
    maxTestsToLog: 3
  },

  // Progress reporter configuration
  progressReporter: {
    allowColor: true
  },

  // Dashboard configuration
  dashboard: {
    reportType: 'full',
    project: 'github.com/fxml4/fxml4',
    version: 'main',
    module: 'frontend'
  }
};

/**
 * Financial trading specific mutation testing configuration
 */
const financialTradingConfig = {
  // High-risk areas that need extra attention
  highRiskAreas: [
    'frontend/src/components/trading/**',
    'frontend/src/services/trading/**',
    'frontend/src/utils/calculations/**',
    'frontend/src/hooks/trading/**'
  ],

  // Authentication and security components
  securityCritical: [
    'frontend/src/components/auth/**',
    'frontend/src/services/auth/**',
    'frontend/src/utils/security/**',
    'frontend/src/contexts/auth/**'
  ],

  // Real-time data components
  performanceCritical: [
    'frontend/src/components/charts/**',
    'frontend/src/services/websocket/**',
    'frontend/src/hooks/realtime/**',
    'frontend/src/utils/streaming/**'
  ],

  // Custom mutation operators for financial applications
  customMutations: {
    // Financial calculation mutations
    financialArithmetic: {
      description: 'Mutations specific to financial calculations',
      operators: ['arithmetic', 'comparison', 'logical'],
      specialCases: ['precision', 'rounding', 'overflow']
    },

    // UI state mutations
    stateManagement: {
      description: 'Mutations for React state and context',
      operators: ['objectLiteral', 'arrayDeclaration', 'conditionalExpression'],
      specialCases: ['useState', 'useEffect', 'useContext']
    },

    // API call mutations
    apiInteraction: {
      description: 'Mutations for API calls and data fetching',
      operators: ['stringLiteral', 'objectLiteral', 'conditionalExpression'],
      specialCases: ['fetch', 'axios', 'websocket']
    }
  },

  // Test patterns specific to trading applications
  testPatterns: {
    tradingComponents: {
      requiredTests: [
        'order placement validation',
        'price display accuracy',
        'position calculation correctness',
        'risk management alerts',
        'real-time data updates'
      ],
      mutationFocus: [
        'input validation',
        'calculation accuracy',
        'state transitions',
        'error handling',
        'boundary conditions'
      ]
    },

    authenticationFlow: {
      requiredTests: [
        'login validation',
        'session management',
        'permission checks',
        'logout behavior',
        'token handling'
      ],
      mutationFocus: [
        'security bypasses',
        'permission escalation',
        'session hijacking',
        'token manipulation',
        'authentication state'
      ]
    },

    dataVisualization: {
      requiredTests: [
        'chart data accuracy',
        'real-time updates',
        'performance under load',
        'error state handling',
        'responsive behavior'
      ],
      mutationFocus: [
        'data transformation',
        'rendering logic',
        'event handling',
        'performance optimizations',
        'accessibility features'
      ]
    }
  }
};

/**
 * Create component-specific configuration
 */
function createComponentConfig(componentName) {
  const baseConfig = { ...config };

  // Adjust configuration based on component
  switch (componentName) {
    case 'trading':
      baseConfig.mutate = [
        'frontend/src/components/trading/**/*.ts',
        'frontend/src/components/trading/**/*.tsx',
        '!**/*.test.*'
      ];
      baseConfig.thresholds = { high: 95, low: 90, break: 85 }; // Higher standards for trading
      break;

    case 'auth':
      baseConfig.mutate = [
        'frontend/src/components/auth/**/*.ts',
        'frontend/src/components/auth/**/*.tsx',
        'frontend/src/services/auth/**/*.ts',
        '!**/*.test.*'
      ];
      baseConfig.thresholds = { high: 95, low: 90, break: 85 }; // Higher standards for security
      break;

    case 'charts':
      baseConfig.mutate = [
        'frontend/src/components/charts/**/*.ts',
        'frontend/src/components/charts/**/*.tsx',
        '!**/*.test.*'
      ];
      baseConfig.timeoutMS = 600000; // 10 minutes for complex chart tests
      break;

    case 'dashboard':
      baseConfig.mutate = [
        'frontend/src/components/dashboard/**/*.ts',
        'frontend/src/components/dashboard/**/*.tsx',
        '!**/*.test.*'
      ];
      break;

    default:
      // Use default configuration
      break;
  }

  return baseConfig;
}

/**
 * Mutation operators specifically designed for financial applications
 */
const financialMutationOperators = {
  arithmeticOperator: {
    description: 'Mutate arithmetic operators in financial calculations',
    examples: ['+', '-', '*', '/', '%', '**'],
    riskLevel: 'high',
    applicableTo: ['price calculations', 'position sizing', 'PnL calculations']
  },

  comparisonOperator: {
    description: 'Mutate comparison operators in validation logic',
    examples: ['>', '<', '>=', '<=', '==', '!=', '===', '!=='],
    riskLevel: 'critical',
    applicableTo: ['risk limits', 'validation rules', 'threshold checks']
  },

  logicalOperator: {
    description: 'Mutate logical operators in conditional logic',
    examples: ['&&', '||', '!'],
    riskLevel: 'high',
    applicableTo: ['authentication', 'authorization', 'validation']
  },

  stringLiteral: {
    description: 'Mutate string literals in API calls and configuration',
    examples: ['""', '"Stryker"', '"Stryker was here!"'],
    riskLevel: 'medium',
    applicableTo: ['API endpoints', 'configuration values', 'error messages']
  },

  numberLiteral: {
    description: 'Mutate number literals in financial constants',
    examples: ['0', '1', '-1', '0.1'],
    riskLevel: 'critical',
    applicableTo: ['financial constants', 'precision values', 'thresholds']
  },

  booleanLiteral: {
    description: 'Mutate boolean literals in feature flags and conditions',
    examples: ['true', 'false'],
    riskLevel: 'high',
    applicableTo: ['feature flags', 'validation results', 'state flags']
  },

  conditionalExpression: {
    description: 'Mutate ternary operators and conditional expressions',
    examples: ['condition ? a : b', 'condition && expression'],
    riskLevel: 'high',
    applicableTo: ['UI state', 'data processing', 'error handling']
  },

  objectLiteral: {
    description: 'Mutate object properties and methods',
    examples: ['{}', '{a: 1}', '{a: 1, b: 2}'],
    riskLevel: 'medium',
    applicableTo: ['configuration objects', 'API payloads', 'component props']
  },

  arrayDeclaration: {
    description: 'Mutate array declarations and operations',
    examples: ['[]', '[1]', '[1, 2]'],
    riskLevel: 'medium',
    applicableTo: ['data collections', 'API responses', 'UI lists']
  }
};

/**
 * Test quality metrics for financial applications
 */
const testQualityMetrics = {
  coverage: {
    minimum: 80,
    target: 90,
    critical_paths: 95
  },

  mutation_score: {
    minimum: 80,
    target: 90,
    security_components: 95,
    trading_components: 95
  },

  performance: {
    test_execution_time: 300, // seconds
    mutation_testing_time: 3600, // seconds (1 hour)
    memory_usage_limit: '2GB'
  },

  quality_gates: {
    failed_tests: 0,
    mutation_survivors: {
      maximum_percentage: 10,
      critical_areas_maximum: 5
    },
    timeout_failures: {
      maximum_percentage: 5
    }
  }
};

module.exports = {
  // Main configuration
  ...config,

  // Helper functions
  createComponentConfig,

  // Financial trading specific configurations
  financialTradingConfig,
  financialMutationOperators,
  testQualityMetrics,

  // Utility functions
  getConfigForComponent: (componentName) => createComponentConfig(componentName),
  getFinancialConfig: () => financialTradingConfig,
  getMutationOperators: () => financialMutationOperators,
  getQualityMetrics: () => testQualityMetrics
};
