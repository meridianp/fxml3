# FXML4 Production Infrastructure Variables

variable "aws_region" {
  description = "AWS region for infrastructure deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Environment must be one of: production, staging, development."
  }
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks allowed to access the EKS cluster API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Restrict this in production
}

# Database Configuration
variable "db_instance_class" {
  description = "RDS instance class for the database"
  type        = string
  default     = "db.r5.xlarge"

  validation {
    condition = can(regex("^db\\.", var.db_instance_class))
    error_message = "DB instance class must start with 'db.'."
  }
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for the database (GB)"
  type        = number
  default     = 500

  validation {
    condition     = var.db_allocated_storage >= 100 && var.db_allocated_storage <= 10000
    error_message = "Database allocated storage must be between 100 and 10000 GB."
  }
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for database auto-scaling (GB)"
  type        = number
  default     = 2000

  validation {
    condition     = var.db_max_allocated_storage >= 100 && var.db_max_allocated_storage <= 10000
    error_message = "Database max allocated storage must be between 100 and 10000 GB."
  }
}

variable "db_backup_retention_days" {
  description = "Number of days to retain database backups"
  type        = number
  default     = 30

  validation {
    condition     = var.db_backup_retention_days >= 7 && var.db_backup_retention_days <= 35
    error_message = "Database backup retention must be between 7 and 35 days."
  }
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"

  validation {
    condition = can(regex("^cache\\.", var.redis_node_type))
    error_message = "Redis node type must start with 'cache.'."
  }
}

variable "redis_num_cache_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 2

  validation {
    condition     = var.redis_num_cache_nodes >= 2 && var.redis_num_cache_nodes <= 6
    error_message = "Redis cache nodes must be between 2 and 6."
  }
}

# Monitoring Configuration
variable "cloudwatch_log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 30

  validation {
    condition = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.cloudwatch_log_retention_days)
    error_message = "CloudWatch log retention must be a valid retention period."
  }
}

variable "prometheus_storage_size" {
  description = "Prometheus storage size (e.g., 100Gi)"
  type        = string
  default     = "100Gi"

  validation {
    condition = can(regex("^[0-9]+Gi$", var.prometheus_storage_size))
    error_message = "Prometheus storage size must be in format like '100Gi'."
  }
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.grafana_admin_password) >= 8
    error_message = "Grafana admin password must be at least 8 characters long."
  }
}

# Application Configuration
variable "api_replica_count" {
  description = "Number of API replicas"
  type        = number
  default     = 3

  validation {
    condition     = var.api_replica_count >= 2 && var.api_replica_count <= 20
    error_message = "API replica count must be between 2 and 20."
  }
}

variable "ui_replica_count" {
  description = "Number of UI replicas"
  type        = number
  default     = 2

  validation {
    condition     = var.ui_replica_count >= 1 && var.ui_replica_count <= 10
    error_message = "UI replica count must be between 1 and 10."
  }
}

# Domain Configuration
variable "domain_name" {
  description = "Primary domain name for the application"
  type        = string
  default     = "fxml4.trading"

  validation {
    condition = can(regex("^[a-z0-9.-]+\\.[a-z]{2,}$", var.domain_name))
    error_message = "Domain name must be a valid domain format."
  }
}

variable "certificate_arn" {
  description = "ARN of the SSL certificate for the domain (optional, will create if not provided)"
  type        = string
  default     = ""
}

# Backup Configuration
variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30

  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 90
    error_message = "Backup retention must be between 7 and 90 days."
  }
}

variable "backup_schedule" {
  description = "Cron expression for backup schedule"
  type        = string
  default     = "0 2 * * *"  # Daily at 2 AM

  validation {
    condition = can(regex("^[0-9*,-/]+ [0-9*,-/]+ [0-9*,-/]+ [0-9*,-/]+ [0-9*,-/]+$", var.backup_schedule))
    error_message = "Backup schedule must be a valid cron expression."
  }
}

# Security Configuration
variable "enable_waf" {
  description = "Enable AWS WAF for the load balancer"
  type        = bool
  default     = true
}

variable "enable_shield" {
  description = "Enable AWS Shield Advanced for DDoS protection"
  type        = bool
  default     = false  # Shield Advanced has additional costs
}

variable "enable_guardduty" {
  description = "Enable AWS GuardDuty for threat detection"
  type        = bool
  default     = true
}

# Notification Configuration
variable "notification_email" {
  description = "Email address for notifications and alerts"
  type        = string
  default     = ""

  validation {
    condition = var.notification_email == "" || can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.notification_email))
    error_message = "Notification email must be a valid email address or empty."
  }
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = ""
  sensitive   = true
}

# Cost Management
variable "auto_scaling_enabled" {
  description = "Enable auto-scaling for cost optimization"
  type        = bool
  default     = true
}

variable "spot_instances_enabled" {
  description = "Enable spot instances for cost optimization (non-production workloads)"
  type        = bool
  default     = false
}

variable "schedule_scaling_enabled" {
  description = "Enable scheduled scaling based on trading hours"
  type        = bool
  default     = true
}

# Trading-specific Configuration
variable "trading_hours_timezone" {
  description = "Timezone for trading hours (e.g., America/New_York)"
  type        = string
  default     = "UTC"
}

variable "market_data_retention_days" {
  description = "Number of days to retain raw market data"
  type        = number
  default     = 90

  validation {
    condition     = var.market_data_retention_days >= 30 && var.market_data_retention_days <= 365
    error_message = "Market data retention must be between 30 and 365 days."
  }
}

variable "enable_paper_trading" {
  description = "Enable paper trading mode"
  type        = bool
  default     = false
}

# Compliance Configuration
variable "enable_audit_logging" {
  description = "Enable comprehensive audit logging"
  type        = bool
  default     = true
}

variable "compliance_mode" {
  description = "Compliance mode (standard, enhanced, strict)"
  type        = string
  default     = "enhanced"

  validation {
    condition     = contains(["standard", "enhanced", "strict"], var.compliance_mode)
    error_message = "Compliance mode must be one of: standard, enhanced, strict."
  }
}

# Performance Configuration
variable "enable_performance_insights" {
  description = "Enable RDS Performance Insights"
  type        = bool
  default     = true
}

variable "enable_enhanced_monitoring" {
  description = "Enable RDS Enhanced Monitoring"
  type        = bool
  default     = true
}

variable "cache_ttl_seconds" {
  description = "Default cache TTL in seconds"
  type        = number
  default     = 300

  validation {
    condition     = var.cache_ttl_seconds >= 60 && var.cache_ttl_seconds <= 3600
    error_message = "Cache TTL must be between 60 and 3600 seconds."
  }
}

# Disaster Recovery Configuration
variable "enable_cross_region_backup" {
  description = "Enable cross-region backup replication"
  type        = bool
  default     = true
}

variable "dr_region" {
  description = "Disaster recovery region"
  type        = string
  default     = "us-west-2"
}

# Development and Testing
variable "enable_debug_mode" {
  description = "Enable debug mode (should be false in production)"
  type        = bool
  default     = false
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}

# Resource Tagging
variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "cost_center" {
  description = "Cost center for billing purposes"
  type        = string
  default     = "Trading-Infrastructure"
}

variable "owner" {
  description = "Owner of the infrastructure"
  type        = string
  default     = "FXML4-Trading-Team"
}
