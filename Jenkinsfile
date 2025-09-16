// FXML4 Jenkins CI/CD Pipeline with Containerized E2E Testing

pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    environment {
        PYTHON_VERSION = '3.12'
        DOCKER_REGISTRY = 'ghcr.io'
        IMAGE_NAME = 'fxml4'
        TEST_RESULTS_DIR = 'test-results'
        COVERAGE_THRESHOLD = '80'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git submodule update --init --recursive'
            }
        }

        stage('Environment Setup') {
            steps {
                echo 'Setting up Python environment...'
                sh '''
                    python${PYTHON_VERSION} -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements-dev.txt
                    pip install -e .
                '''
            }
        }

        stage('Code Quality') {
            parallel {
                stage('Linting') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            make lint
                        '''
                    }
                }

                stage('Security Scan') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            python scripts/validate_security.py
                        '''
                    }
                }
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    make test-unit
                '''
            }
            post {
                always {
                    junit "${TEST_RESULTS_DIR}/unit-results.xml"
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: "${TEST_RESULTS_DIR}/coverage-html",
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report',
                        reportTitles: 'Test Coverage'
                    ])
                }
            }
        }

        stage('Integration Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    make test-integration
                '''
            }
            post {
                always {
                    junit "${TEST_RESULTS_DIR}/integration-results.xml"
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                echo 'Building Docker test images...'
                sh '''
                    docker-compose -f docker-compose.test.yml build
                '''
            }
        }

        stage('E2E Tests') {
            steps {
                echo 'Running containerized E2E tests...'
                sh '''
                    ./scripts/run_e2e_auth_tests.sh run
                '''
            }
            post {
                always {
                    sh 'docker-compose -f docker-compose.test.yml down -v --remove-orphans || true'
                    archiveArtifacts artifacts: "${TEST_RESULTS_DIR}/**/*", allowEmptyArchive: true
                }
            }
        }

        stage('Performance Tests') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    . venv/bin/activate
                    make test-performance
                '''
            }
            post {
                always {
                    junit "${TEST_RESULTS_DIR}/performance-results.xml"
                }
            }
        }

        stage('Coverage Check') {
            steps {
                sh '''
                    . venv/bin/activate
                    make coverage-check
                '''
            }
        }

        stage('Generate Reports') {
            steps {
                sh '''
                    . venv/bin/activate
                    python scripts/run_integrated_test_pipeline.py --ci
                '''

                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: "${TEST_RESULTS_DIR}",
                    reportFiles: 'summary.txt',
                    reportName: 'Test Summary',
                    reportTitles: 'Pipeline Summary'
                ])
            }
        }

        stage('Deploy to Staging') {
            when {
                branch 'develop'
            }
            steps {
                echo 'Deploying to staging environment...'
                sh '''
                    docker-compose -f docker-compose.prod.yml build
                    # Add deployment steps here
                '''
            }
        }

        stage('Deploy to Production') {
            when {
                branch 'main'
                expression { currentBuild.result == null || currentBuild.result == 'SUCCESS' }
            }
            steps {
                input message: 'Deploy to production?', ok: 'Deploy'
                echo 'Deploying to production environment...'
                sh '''
                    # Add production deployment steps here
                    echo "Deployment would happen here"
                '''
            }
        }
    }

    post {
        always {
            echo 'Cleaning up workspace...'
            sh '''
                docker-compose -f docker-compose.test.yml down -v --remove-orphans || true
                find . -type d -name "__pycache__" -exec rm -rf {} + || true
                find . -type f -name "*.pyc" -delete || true
            '''

            emailext(
                subject: "${currentBuild.currentResult}: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
                body: """
                    <p>Build Status: ${currentBuild.currentResult}</p>
                    <p>Build Number: ${env.BUILD_NUMBER}</p>
                    <p>Branch: ${env.BRANCH_NAME}</p>
                    <p>Check console output at <a href='${env.BUILD_URL}'>${env.BUILD_URL}</a></p>
                """,
                recipientProviders: [developers()],
                mimeType: 'text/html'
            )
        }

        success {
            echo 'Pipeline completed successfully!'
            slackSend(
                color: 'good',
                message: "✅ Build Successful: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
            )
        }

        failure {
            echo 'Pipeline failed!'
            slackSend(
                color: 'danger',
                message: "❌ Build Failed: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
            )
        }

        unstable {
            echo 'Pipeline is unstable!'
            slackSend(
                color: 'warning',
                message: "⚠️ Build Unstable: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
            )
        }
    }
}
