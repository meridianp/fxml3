/**
 * AI Test Safety Framework for Financial Trading Systems
 *
 * Implements comprehensive safety controls, human-in-the-loop validation,
 * and audit trails to ensure AI-generated test insights meet strict
 * financial industry standards for reliability and compliance.
 */

export interface SafetyRule {
  id: string;
  name: string;
  description: string;
  category: 'financial_accuracy' | 'regulatory_compliance' | 'risk_management' | 'data_integrity';
  severity: 'blocking' | 'warning' | 'advisory';
  condition: (context: SafetyValidationContext) => boolean;
  message: string;
  remediation: string;
  enabled: boolean;
}

export interface SafetyValidationContext {
  insight?: any;
  testData?: any;
  scenario?: any;
  codeChanges?: string[];
  userRole?: string;
  environment?: 'development' | 'testing' | 'staging' | 'production';
  metadata?: Record<string, any>;
}

export interface ValidationResult {
  passed: boolean;
  violations: SafetyViolation[];
  warnings: SafetyWarning[];
  recommendations: string[];
  requiresHumanApproval: boolean;
  approvalLevel: 'junior' | 'senior' | 'lead' | 'compliance';
  riskScore: number; // 0-100
}

export interface SafetyViolation {
  ruleId: string;
  ruleName: string;
  severity: 'blocking' | 'warning';
  message: string;
  remediation: string;
  context: Record<string, any>;
}

export interface SafetyWarning {
  ruleId: string;
  message: string;
  recommendation: string;
}

export interface ApprovalRequest {
  id: string;
  type: 'insight_approval' | 'scenario_approval' | 'test_generation' | 'data_modification';
  requestedBy: string;
  requestedAt: number;
  requiredApprovalLevel: string;
  content: any;
  justification: string;
  riskAssessment: {
    score: number;
    factors: string[];
    mitigations: string[];
  };
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  approvedBy?: string;
  approvedAt?: number;
  rejectionReason?: string;
  expiresAt: number;
}

export interface ComplianceCheck {
  regulation: string;
  requirement: string;
  status: 'compliant' | 'violation' | 'review_required';
  evidence: string[];
  gaps: string[];
}

/**
 * Core safety framework for AI testing in financial systems
 */
export class AITestSafetyFramework {
  private rules: Map<string, SafetyRule> = new Map();
  private approvalQueue: Map<string, ApprovalRequest> = new Map();
  private complianceChecks: ComplianceCheck[] = [];
  private auditLog: Array<{
    timestamp: number;
    action: string;
    user?: string;
    details: Record<string, any>;
    riskLevel: 'low' | 'medium' | 'high' | 'critical';
  }> = [];

  constructor() {
    this.initializeDefaultRules();
    this.initializeComplianceChecks();
  }

  /**
   * Validate AI-generated content against safety rules
   */
  validateContent(
    content: any,
    type: 'insight' | 'scenario' | 'test_data' | 'recommendation',
    context: SafetyValidationContext
  ): ValidationResult {
    const violations: SafetyViolation[] = [];
    const warnings: SafetyWarning[] = [];
    const recommendations: string[] = [];

    let riskScore = 0;
    let requiresHumanApproval = false;
    let approvalLevel: ValidationResult['approvalLevel'] = 'junior';

    // Run all enabled rules
    this.rules.forEach(rule => {
      if (!rule.enabled) return;

      try {
        const ruleContext = { ...context, [type]: content };

        if (rule.condition(ruleContext)) {
          if (rule.severity === 'blocking') {
            violations.push({
              ruleId: rule.id,
              ruleName: rule.name,
              severity: 'blocking',
              message: rule.message,
              remediation: rule.remediation,
              context: ruleContext
            });
            riskScore += 25;
            requiresHumanApproval = true;
            approvalLevel = this.escalateApprovalLevel(approvalLevel, 'senior');
          } else if (rule.severity === 'warning') {
            violations.push({
              ruleId: rule.id,
              ruleName: rule.name,
              severity: 'warning',
              message: rule.message,
              remediation: rule.remediation,
              context: ruleContext
            });
            riskScore += 10;
            requiresHumanApproval = true;
          } else {
            warnings.push({
              ruleId: rule.id,
              message: rule.message,
              recommendation: rule.remediation
            });
            riskScore += 5;
          }

          // Category-specific escalation
          if (rule.category === 'financial_accuracy' || rule.category === 'regulatory_compliance') {
            approvalLevel = this.escalateApprovalLevel(approvalLevel, 'compliance');
          }
        }
      } catch (error) {
        this.logAuditEvent('rule_execution_error', undefined, {
          ruleId: rule.id,
          error: error instanceof Error ? error.message : 'Unknown error'
        }, 'medium');
      }
    });

    // Generate recommendations based on violations
    if (violations.length > 0) {
      recommendations.push('Review and address all safety violations before proceeding');
    }
    if (warnings.length > 0) {
      recommendations.push('Consider addressing warnings to improve reliability');
    }
    if (riskScore > 50) {
      recommendations.push('High risk score detected - requires senior review');
      approvalLevel = this.escalateApprovalLevel(approvalLevel, 'lead');
    }

    // Final risk score calculation
    riskScore = Math.min(100, riskScore);

    const result: ValidationResult = {
      passed: violations.filter(v => v.severity === 'blocking').length === 0,
      violations,
      warnings,
      recommendations,
      requiresHumanApproval,
      approvalLevel,
      riskScore
    };

    this.logAuditEvent('safety_validation', context.userRole, {
      type,
      passed: result.passed,
      riskScore,
      violationsCount: violations.length,
      warningsCount: warnings.length
    }, riskScore > 50 ? 'high' : riskScore > 25 ? 'medium' : 'low');

    return result;
  }

  /**
   * Submit request for human approval
   */
  requestApproval(
    type: ApprovalRequest['type'],
    content: any,
    justification: string,
    requestedBy: string,
    context: SafetyValidationContext
  ): string {
    const validation = this.validateContent(content, type.split('_')[0] as any, context);

    const approvalRequest: ApprovalRequest = {
      id: this.generateApprovalId(),
      type,
      requestedBy,
      requestedAt: Date.now(),
      requiredApprovalLevel: validation.approvalLevel,
      content,
      justification,
      riskAssessment: {
        score: validation.riskScore,
        factors: [
          ...validation.violations.map(v => `${v.severity}: ${v.ruleName}`),
          ...validation.warnings.map(w => `Warning: ${w.ruleId}`)
        ],
        mitigations: validation.recommendations
      },
      status: 'pending',
      expiresAt: Date.now() + (24 * 60 * 60 * 1000) // 24 hours
    };

    this.approvalQueue.set(approvalRequest.id, approvalRequest);

    this.logAuditEvent('approval_requested', requestedBy, {
      approvalId: approvalRequest.id,
      type,
      riskScore: validation.riskScore,
      requiredLevel: validation.approvalLevel
    }, validation.riskScore > 50 ? 'high' : 'medium');

    return approvalRequest.id;
  }

  /**
   * Process approval decision
   */
  processApproval(
    approvalId: string,
    decision: 'approved' | 'rejected',
    approver: string,
    approverRole: string,
    notes?: string
  ): boolean {
    const request = this.approvalQueue.get(approvalId);
    if (!request) {
      throw new Error('Approval request not found');
    }

    if (request.status !== 'pending') {
      throw new Error('Approval request is not pending');
    }

    if (Date.now() > request.expiresAt) {
      request.status = 'expired';
      throw new Error('Approval request has expired');
    }

    // Validate approver has sufficient authority
    if (!this.hasApprovalAuthority(approverRole, request.requiredApprovalLevel)) {
      throw new Error(`Insufficient approval authority. Required: ${request.requiredApprovalLevel}, Provided: ${approverRole}`);
    }

    request.status = decision;
    request.approvedBy = approver;
    request.approvedAt = Date.now();

    if (decision === 'rejected') {
      request.rejectionReason = notes || 'No reason provided';
    }

    this.logAuditEvent('approval_processed', approver, {
      approvalId,
      decision,
      requiredLevel: request.requiredApprovalLevel,
      approverRole,
      notes
    }, request.riskAssessment.score > 50 ? 'high' : 'medium');

    return decision === 'approved';
  }

  /**
   * Get pending approval requests for a user role
   */
  getPendingApprovals(userRole: string): ApprovalRequest[] {
    const now = Date.now();
    const pending: ApprovalRequest[] = [];

    this.approvalQueue.forEach(request => {
      if (request.status === 'pending' && request.expiresAt > now) {
        if (this.hasApprovalAuthority(userRole, request.requiredApprovalLevel)) {
          pending.push(request);
        }
      } else if (request.expiresAt <= now && request.status === 'pending') {
        // Mark expired
        request.status = 'expired';
      }
    });

    return pending.sort((a, b) => b.riskAssessment.score - a.riskAssessment.score);
  }

  /**
   * Run compliance checks
   */
  runComplianceChecks(context: SafetyValidationContext): ComplianceCheck[] {
    const results: ComplianceCheck[] = [];

    this.complianceChecks.forEach(check => {
      const result = { ...check };

      // Simulate compliance checking logic
      // In production, this would integrate with actual compliance systems
      if (context.environment === 'production' && !context.userRole?.includes('compliance')) {
        result.status = 'review_required';
        result.gaps = ['Production deployment requires compliance officer approval'];
      }

      results.push(result);
    });

    return results;
  }

  /**
   * Get audit log with filtering
   */
  getAuditLog(filter?: {
    user?: string;
    action?: string;
    riskLevel?: string;
    limit?: number;
    since?: number;
  }): typeof this.auditLog {
    let filtered = [...this.auditLog];

    if (filter?.user) {
      filtered = filtered.filter(entry => entry.user === filter.user);
    }
    if (filter?.action) {
      filtered = filtered.filter(entry => entry.action === filter.action);
    }
    if (filter?.riskLevel) {
      filtered = filtered.filter(entry => entry.riskLevel === filter.riskLevel);
    }
    if (filter?.since) {
      filtered = filtered.filter(entry => entry.timestamp >= filter.since!);
    }

    filtered.sort((a, b) => b.timestamp - a.timestamp);

    if (filter?.limit) {
      filtered = filtered.slice(0, filter.limit);
    }

    return filtered;
  }

  /**
   * Export safety report for compliance
   */
  generateSafetyReport(period: { start: number; end: number }): {
    summary: {
      totalValidations: number;
      passedValidations: number;
      blockedActions: number;
      approvalRequests: number;
      averageRiskScore: number;
    };
    violations: SafetyViolation[];
    approvals: ApprovalRequest[];
    complianceStatus: ComplianceCheck[];
    auditTrail: typeof this.auditLog;
  } {
    const auditEntries = this.getAuditLog({ since: period.start });
    const validations = auditEntries.filter(e => e.action === 'safety_validation');
    const approvals = Array.from(this.approvalQueue.values()).filter(
      a => a.requestedAt >= period.start && a.requestedAt <= period.end
    );

    return {
      summary: {
        totalValidations: validations.length,
        passedValidations: validations.filter(v => v.details.passed).length,
        blockedActions: validations.filter(v => !v.details.passed).length,
        approvalRequests: approvals.length,
        averageRiskScore: validations.reduce((sum, v) => sum + (v.details.riskScore || 0), 0) / validations.length || 0
      },
      violations: [], // Would be populated from stored violations
      approvals,
      complianceStatus: this.complianceChecks,
      auditTrail: auditEntries
    };
  }

  // Private helper methods

  private initializeDefaultRules(): void {
    const defaultRules: SafetyRule[] = [
      {
        id: 'financial_calculation_accuracy',
        name: 'Financial Calculation Accuracy',
        description: 'Ensures AI-generated test data maintains financial calculation accuracy',
        category: 'financial_accuracy',
        severity: 'blocking',
        condition: (ctx) => {
          // Check if AI is modifying financial calculations without proper validation
          return ctx.testData?.type === 'financial_calculation' &&
                 !ctx.metadata?.validated_by_finance_team;
        },
        message: 'Financial calculation modifications require finance team validation',
        remediation: 'Submit for finance team review before implementation',
        enabled: true
      },
      {
        id: 'regulatory_compliance_sox',
        name: 'SOX Compliance Check',
        description: 'Validates compliance with Sarbanes-Oxley financial reporting requirements',
        category: 'regulatory_compliance',
        severity: 'blocking',
        condition: (ctx) => {
          return ctx.environment === 'production' &&
                 ctx.insight?.type === 'financial_reporting' &&
                 !ctx.metadata?.sox_approved;
        },
        message: 'Production financial reporting changes require SOX compliance approval',
        remediation: 'Obtain SOX compliance officer approval',
        enabled: true
      },
      {
        id: 'risk_limit_validation',
        name: 'Risk Limit Validation',
        description: 'Ensures test scenarios do not exceed defined risk limits',
        category: 'risk_management',
        severity: 'warning',
        condition: (ctx) => {
          return ctx.scenario?.riskLevel === 'extreme' &&
                 ctx.environment !== 'testing';
        },
        message: 'Extreme risk scenarios should only be used in testing environment',
        remediation: 'Limit extreme risk scenarios to testing environment or get approval',
        enabled: true
      },
      {
        id: 'data_integrity_check',
        name: 'Data Integrity Validation',
        description: 'Validates data consistency and integrity in AI-generated content',
        category: 'data_integrity',
        severity: 'warning',
        condition: (ctx) => {
          return ctx.testData?.confidence < 80;
        },
        message: 'Low confidence AI-generated data detected',
        remediation: 'Review and validate low-confidence AI predictions manually',
        enabled: true
      },
      {
        id: 'production_deployment_guard',
        name: 'Production Deployment Safety',
        description: 'Prevents AI modifications in production without proper approvals',
        category: 'risk_management',
        severity: 'blocking',
        condition: (ctx) => {
          return ctx.environment === 'production' &&
                 !ctx.userRole?.includes('senior') &&
                 ctx.insight?.impact === 'high';
        },
        message: 'High-impact production changes require senior approval',
        remediation: 'Escalate to senior team member for approval',
        enabled: true
      }
    ];

    defaultRules.forEach(rule => this.rules.set(rule.id, rule));
  }

  private initializeComplianceChecks(): void {
    this.complianceChecks = [
      {
        regulation: 'SOX (Sarbanes-Oxley)',
        requirement: 'Financial data accuracy and audit trails',
        status: 'compliant',
        evidence: ['Audit logs enabled', 'Financial calculation validation'],
        gaps: []
      },
      {
        regulation: 'GDPR',
        requirement: 'Data privacy and consent management',
        status: 'compliant',
        evidence: ['Data anonymization', 'Consent tracking'],
        gaps: []
      },
      {
        regulation: 'MiFID II',
        requirement: 'Trading system reliability and monitoring',
        status: 'compliant',
        evidence: ['Performance monitoring', 'Risk controls'],
        gaps: []
      }
    ];
  }

  private escalateApprovalLevel(
    current: ValidationResult['approvalLevel'],
    required: ValidationResult['approvalLevel']
  ): ValidationResult['approvalLevel'] {
    const levels = ['junior', 'senior', 'lead', 'compliance'];
    const currentIndex = levels.indexOf(current);
    const requiredIndex = levels.indexOf(required);

    return levels[Math.max(currentIndex, requiredIndex)] as ValidationResult['approvalLevel'];
  }

  private hasApprovalAuthority(userRole: string, requiredLevel: string): boolean {
    const authorityMap: Record<string, string[]> = {
      'junior': ['junior'],
      'senior': ['junior', 'senior'],
      'lead': ['junior', 'senior', 'lead'],
      'compliance': ['junior', 'senior', 'lead', 'compliance']
    };

    const userAuthority = authorityMap[userRole] || ['junior'];
    return userAuthority.includes(requiredLevel);
  }

  private generateApprovalId(): string {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substr(2, 9);
    return `approval_${timestamp}_${random}`;
  }

  private logAuditEvent(
    action: string,
    user: string | undefined,
    details: Record<string, any>,
    riskLevel: 'low' | 'medium' | 'high' | 'critical'
  ): void {
    this.auditLog.push({
      timestamp: Date.now(),
      action,
      user,
      details,
      riskLevel
    });

    // Keep only last 10000 entries to prevent memory issues
    if (this.auditLog.length > 10000) {
      this.auditLog = this.auditLog.slice(-10000);
    }
  }
}

/**
 * Singleton instance for global access
 */
export const aiTestSafetyFramework = new AITestSafetyFramework();
