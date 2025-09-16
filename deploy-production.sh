#!/bin/bash

# FXML4 Production Deployment Script
# This script deploys the FXML4 system using Docker Compose for production

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to set compose command
set_compose_command() {
    if command_exists docker-compose; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi
}

# Function to check system requirements
check_requirements() {
    print_status "Checking system requirements..."

    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    # Check Docker version
    DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    print_status "Docker version: $DOCKER_VERSION"

    # Check Docker Compose version
    set_compose_command
    if [[ "$COMPOSE_CMD" == "docker-compose" ]]; then
        COMPOSE_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    else
        COMPOSE_VERSION=$(docker compose version | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    fi
    print_status "Docker Compose version: $COMPOSE_VERSION"

    # Check available disk space (minimum 10GB)
    AVAILABLE_SPACE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$AVAILABLE_SPACE" -lt 10 ]; then
        print_warning "Available disk space is less than 10GB. Consider freeing up space."
    fi

    print_success "System requirements check passed"
}

# Function to check environment configuration
check_environment() {
    print_status "Checking environment configuration..."

    if [ ! -f .env.production ]; then
        print_error ".env.production file not found!"
        print_status "Please copy .env.production.template to .env.production and configure it."
        exit 1
    fi

    # Check for critical environment variables
    source .env.production

    CRITICAL_VARS=(
        "FXML4_JWT_SECRET_KEY"
        "FXML4_DATABASE_PASSWORD"
        "REDIS_PASSWORD"
        "RABBITMQ_PASSWORD"
        "POLYGON_API_KEY"
        "ALPHA_VANTAGE_API_KEY"
    )

    for var in "${CRITICAL_VARS[@]}"; do
        if [ -z "${!var}" ] || [ "${!var}" = "your-"* ]; then
            print_error "Critical environment variable $var is not set or contains default value"
            exit 1
        fi
    done

    print_success "Environment configuration check passed"
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."

    mkdir -p data/{cache,features,historical,processed,polygon_cache}
    mkdir -p models/{EURUSD,GBPUSD,USDCHF,USDJPY}
    mkdir -p logs
    mkdir -p config
    mkdir -p monitoring/{prometheus,grafana,loki,promtail}
    mkdir -p nginx/{ssl,logs}
    mkdir -p db/backups

    print_success "Directories created successfully"
}

# Function to setup monitoring configuration
setup_monitoring() {
    print_status "Setting up monitoring configuration..."

    # Create Prometheus configuration
    cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'fxml4-api'
    static_configs:
      - targets: ['api:9090']
    scrape_interval: 5s
    metrics_path: /metrics

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'rabbitmq'
    static_configs:
      - targets: ['rabbitmq:15692']

alerting:
  alertmanagers:
    - static_configs:
        - targets: []
EOF

    # Create Grafana datasource configuration
    mkdir -p monitoring/grafana/provisioning/{datasources,dashboards}

    cat > monitoring/grafana/provisioning/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

    print_success "Monitoring configuration setup completed"
}

# Function to setup nginx configuration
setup_nginx() {
    print_status "Setting up Nginx configuration..."

    cat > nginx/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    upstream dashboard {
        server dashboard:8501;
    }

    server {
        listen 80;
        server_name localhost;

        location /api/ {
            proxy_pass http://api/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }

        location /dashboard/ {
            proxy_pass http://dashboard/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }

        location / {
            proxy_pass http://dashboard/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
}
EOF

    print_success "Nginx configuration setup completed"
}

# Function to build and start services
deploy_services() {
    print_status "Building and starting services..."

    # Determine compose file to use
    if [ "${FXML4_ENV:-production}" = "development" ]; then
        COMPOSE_FILE="docker-compose.local.yml"
        print_status "Using local development setup"
    else
        COMPOSE_FILE="docker-compose.prod.yml"
        print_status "Using production setup"

        # Try to pull images, but don't fail if they don't exist
        print_status "Attempting to pull existing images..."
        $COMPOSE_CMD -f $COMPOSE_FILE pull --ignore-pull-failures || true
    fi

    # Build services
    print_status "Building services..."
    $COMPOSE_CMD -f $COMPOSE_FILE build --no-cache

    # Start services
    print_status "Starting services..."
    $COMPOSE_CMD -f $COMPOSE_FILE up -d

    print_success "Services deployed successfully"
}

# Function to wait for services to be ready
wait_for_services() {
    print_status "Waiting for services to be ready..."

    # Wait for API to be ready
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            print_success "API service is ready"
            break
        fi

        attempt=$((attempt + 1))
        print_status "Waiting for API service... ($attempt/$max_attempts)"
        sleep 10
    done

    if [ $attempt -eq $max_attempts ]; then
        print_error "API service failed to start within expected time"
        exit 1
    fi

    print_success "All services are ready"
}

# Function to show service status
show_status() {
    # Determine compose file to use
    if [ "${FXML4_ENV:-production}" = "development" ]; then
        COMPOSE_FILE="docker-compose.local.yml"
    else
        COMPOSE_FILE="docker-compose.prod.yml"
    fi

    print_status "Service Status:"
    $COMPOSE_CMD -f $COMPOSE_FILE ps

    echo ""
    print_status "Access URLs:"
    echo "  API: http://localhost:8000"
    echo "  Dashboard: http://localhost:8501"
    echo "  Grafana: http://localhost:3000"
    echo "  Prometheus: http://localhost:9090"
    echo "  RabbitMQ Management: http://localhost:15672"
    echo ""

    print_status "Logs:"
    echo "  View all logs: $COMPOSE_CMD -f docker-compose.prod.yml logs -f"
    echo "  View API logs: $COMPOSE_CMD -f docker-compose.prod.yml logs -f api"
    echo "  View worker logs: $COMPOSE_CMD -f docker-compose.prod.yml logs -f worker"
}

# Function to setup log rotation
setup_log_rotation() {
    print_status "Setting up log rotation..."

    # Create logrotate configuration
    cat > /tmp/fxml4-logrotate << EOF
/home/\$USER/code/fxml4/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 \$USER \$USER
    postrotate
        $COMPOSE_CMD -f docker-compose.prod.yml restart api dashboard worker
    endscript
}
EOF

    # Install logrotate configuration (requires sudo)
    if command_exists sudo; then
        sudo cp /tmp/fxml4-logrotate /etc/logrotate.d/fxml4
        print_success "Log rotation configured"
    else
        print_warning "Could not install log rotation (sudo not available)"
    fi
}

# Function to create backup script
create_backup_script() {
    print_status "Creating backup script..."

    cat > backup.sh << 'EOF'
#!/bin/bash
# FXML4 Backup Script

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup application data
echo "Backing up application data..."
cp -r data "$BACKUP_DIR/"
cp -r models "$BACKUP_DIR/"
cp -r config "$BACKUP_DIR/"

# Backup database (if using external database)
if [ -n "$DB_HOST" ] && [ "$DB_HOST" != "db" ]; then
    echo "Backing up database..."
    pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_DIR/database.sql"
fi

# Create archive
echo "Creating archive..."
tar -czf "$BACKUP_DIR.tar.gz" -C "$BACKUP_DIR" .
rm -rf "$BACKUP_DIR"

echo "Backup completed: $BACKUP_DIR.tar.gz"
EOF

    chmod +x backup.sh
    print_success "Backup script created"
}

# Main deployment function
main() {
    print_status "Starting FXML4 production deployment..."

    check_requirements
    check_environment
    create_directories
    setup_monitoring
    setup_nginx
    deploy_services
    wait_for_services
    setup_log_rotation
    create_backup_script

    print_success "Production deployment completed successfully!"
    show_status
}

# Handle script arguments
case "${1:-deploy}" in
    deploy)
        main
        ;;
    status)
        set_compose_command
        show_status
        ;;
    logs)
        set_compose_command
        $COMPOSE_CMD -f docker-compose.prod.yml logs -f
        ;;
    stop)
        set_compose_command
        print_status "Stopping services..."
        $COMPOSE_CMD -f docker-compose.prod.yml down
        print_success "Services stopped"
        ;;
    restart)
        set_compose_command
        print_status "Restarting services..."
        $COMPOSE_CMD -f docker-compose.prod.yml restart
        print_success "Services restarted"
        ;;
    backup)
        source .env.production
        ./backup.sh
        ;;
    *)
        echo "Usage: $0 {deploy|status|logs|stop|restart|backup}"
        exit 1
        ;;
esac
