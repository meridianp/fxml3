/**
 * Help Page
 *
 * Documentation and support for FXML4 platform
 */

'use client';

import { useState } from 'react';
import {
  QuestionMarkCircleIcon,
  BookOpenIcon,
  VideoCameraIcon,
  ChatBubbleLeftRightIcon,
  BugAntIcon,
  LightBulbIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ArrowTopRightOnSquareIcon
} from '@heroicons/react/24/outline';

const helpCategories = [
  {
    title: 'Getting Started',
    icon: LightBulbIcon,
    items: [
      'Platform Overview',
      'Setting Up Your Account',
      'First Time Login',
      'Basic Navigation',
      'Understanding the Dashboard'
    ]
  },
  {
    title: 'Trading',
    icon: ChatBubbleLeftRightIcon,
    items: [
      'Placing Your First Order',
      'Understanding Order Types',
      'Managing Positions',
      'Risk Management',
      'Reading Market Data'
    ]
  },
  {
    title: 'ML & Backtesting',
    icon: BookOpenIcon,
    items: [
      'Creating ML Models',
      'Training Strategies',
      'Running Backtests',
      'Analyzing Results',
      'Optimization Tips'
    ]
  },
  {
    title: 'Technical Support',
    icon: BugAntIcon,
    items: [
      'Connection Issues',
      'Data Feed Problems',
      'API Integration',
      'Performance Optimization',
      'Troubleshooting Guide'
    ]
  }
];

const faqItems = [
  {
    question: 'How do I connect my broker account?',
    answer: 'Go to Settings > API & Data, then follow the broker-specific setup instructions. You\'ll need API credentials from your broker.'
  },
  {
    question: 'Can I use paper trading to test strategies?',
    answer: 'Yes, FXML4 supports paper trading. Enable it in Settings > Trading to test strategies without real money.'
  },
  {
    question: 'How accurate are the ML predictions?',
    answer: 'ML model accuracy varies by market conditions and model type. Historical accuracy is shown in the model details, but past performance doesn\'t guarantee future results.'
  },
  {
    question: 'What data sources does FXML4 support?',
    answer: 'FXML4 supports Interactive Brokers, FXCM, Polygon.io, and other major data providers. See the Data Management section for full details.'
  },
  {
    question: 'How do I backup my strategies and models?',
    answer: 'Use the Export function in each module, or go to Settings > Account to download your complete trading data.'
  }
];

export default function HelpPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedFAQ, setExpandedFAQ] = useState<number | null>(null);
  const [selectedCategory, setSelectedCategory] = useState(helpCategories[0]);

  const filteredCategories = helpCategories.filter(category =>
    category.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    category.items.some(item => item.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const filteredFAQ = faqItems.filter(item =>
    item.question.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.answer.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Help & Documentation</h1>
        <p className="text-gray-400">Find answers and learn how to use FXML4 effectively</p>
      </div>

      {/* Search */}
      <div className="relative mb-8">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search help articles, FAQs, and guides..."
          className="w-full pl-10 pr-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 sticky top-24">
            <h3 className="font-semibold text-white mb-4">Categories</h3>
            <nav className="space-y-2">
              {filteredCategories.map((category) => (
                <button
                  key={category.title}
                  onClick={() => setSelectedCategory(category)}
                  className={`w-full text-left p-3 rounded-lg transition-colors flex items-center gap-3 ${
                    selectedCategory.title === category.title
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <category.icon className="w-5 h-5" />
                  <span>{category.title}</span>
                </button>
              ))}
            </nav>

            {/* Quick Links */}
            <div className="mt-8 pt-6 border-t border-gray-700">
              <h4 className="font-semibold text-white mb-3">Quick Links</h4>
              <div className="space-y-2">
                <a href="#" className="flex items-center gap-2 text-gray-400 hover:text-white text-sm transition-colors">
                  <VideoCameraIcon className="w-4 h-4" />
                  Video Tutorials
                  <ArrowTopRightOnSquareIcon className="w-3 h-3" />
                </a>
                <a href="#" className="flex items-center gap-2 text-gray-400 hover:text-white text-sm transition-colors">
                  <BookOpenIcon className="w-4 h-4" />
                  API Documentation
                  <ArrowTopRightOnSquareIcon className="w-3 h-3" />
                </a>
                <a href="#" className="flex items-center gap-2 text-gray-400 hover:text-white text-sm transition-colors">
                  <ChatBubbleLeftRightIcon className="w-4 h-4" />
                  Community Forum
                  <ArrowTopRightOnSquareIcon className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3 space-y-8">
          {/* Selected Category Articles */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-6">
              <selectedCategory.icon className="w-6 h-6 text-blue-400" />
              <h2 className="text-xl font-semibold text-white">{selectedCategory.title}</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {selectedCategory.items.map((item, index) => (
                <a
                  key={index}
                  href="#"
                  className="p-4 bg-gray-800/50 rounded-lg hover:bg-gray-800 transition-colors group"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-white group-hover:text-blue-400 transition-colors">{item}</span>
                    <ArrowTopRightOnSquareIcon className="w-4 h-4 text-gray-400 group-hover:text-blue-400 transition-colors" />
                  </div>
                </a>
              ))}
            </div>
          </div>

          {/* FAQ Section */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-3">
              <QuestionMarkCircleIcon className="w-6 h-6 text-green-400" />
              Frequently Asked Questions
            </h2>

            <div className="space-y-4">
              {filteredFAQ.map((item, index) => (
                <div key={index} className="border border-gray-700 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setExpandedFAQ(expandedFAQ === index ? null : index)}
                    className="w-full p-4 text-left bg-gray-800/50 hover:bg-gray-800 transition-colors flex items-center justify-between"
                  >
                    <span className="font-medium text-white">{item.question}</span>
                    <ChevronDownIcon
                      className={`w-5 h-5 text-gray-400 transition-transform ${
                        expandedFAQ === index ? 'rotate-180' : ''
                      }`}
                    />
                  </button>

                  {expandedFAQ === index && (
                    <div className="p-4 bg-gray-900 border-t border-gray-700">
                      <p className="text-gray-300 leading-relaxed">{item.answer}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Contact Support */}
          <div className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 border border-blue-500/30 rounded-lg p-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center">
                <ChatBubbleLeftRightIcon className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Need More Help?</h3>
                <p className="text-gray-400">Our support team is here to help you succeed</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <a
                href="#"
                className="p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors text-center"
              >
                <ChatBubbleLeftRightIcon className="w-8 h-8 text-blue-400 mx-auto mb-2" />
                <div className="text-white font-medium">Live Chat</div>
                <div className="text-gray-400 text-sm">Get instant help</div>
              </a>

              <a
                href="#"
                className="p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors text-center"
              >
                <BookOpenIcon className="w-8 h-8 text-green-400 mx-auto mb-2" />
                <div className="text-white font-medium">Email Support</div>
                <div className="text-gray-400 text-sm">Detailed assistance</div>
              </a>

              <a
                href="#"
                className="p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors text-center"
              >
                <VideoCameraIcon className="w-8 h-8 text-purple-400 mx-auto mb-2" />
                <div className="text-white font-medium">Schedule Call</div>
                <div className="text-gray-400 text-sm">Personalized help</div>
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
