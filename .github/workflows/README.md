# FXML4 GitHub Actions Workflows

## Active Workflows

### `comprehensive-testing.yml`
**Primary CI/CD Pipeline** - Consolidated, comprehensive testing workflow with logical stage progression:

1. **Stage 1: Pre-Flight Checks** (Parallel)
   - Code quality validation (linting, formatting, type checking)
   - Security scanning and vulnerability assessment
   - Dependency health check

2. **Stage 2: Core Testing** (Sequential)
   - Unit tests with coverage reporting
   - Integration tests with database services
   - Security and authentication validation

3. **Stage 3: End-to-End Testing** (Sequential)
   - Containerized E2E authentication flows
   - Frontend-backend integration testing
   - Performance regression with baseline comparison

4. **Stage 4: Advanced Testing** (Conditional)
   - Load testing and stress tests (main branch or performance label)
   - Browser compatibility testing (main branch or frontend label)

5. **Stage 5: Build & Security Validation** (Parallel)
   - Docker image build validation
   - Comprehensive security audit
   - Documentation generation and validation

6. **Stage 6: Deployment** (Conditional - main branch only)
   - Container image build and push to registry
   - Staging environment deployment with health checks

### Key Features

- **Logical Dependencies**: Each stage builds on previous stage success
- **Fail-Fast**: Early termination on critical failures saves CI resources
- **Performance Optimized**: Strategic caching and parallel execution where safe
- **Environment-Aware**: Different behaviors for PRs vs main branch
- **Comprehensive Coverage**: 145+ API endpoints, E2E tests, performance regression
- **Rich Reporting**: JUnit XML, coverage reports, performance baselines, security audits

### Trigger Conditions

- **Push**: `main`, `develop` branches
- **Pull Request**: targeting `main` branch
- **Conditional Stages**: 
  - Advanced testing runs on main branch or with specific PR labels
  - Deployment only runs on main branch with successful tests

## Archived Workflows

The following workflows have been consolidated into `comprehensive-testing.yml` and moved to `/archive/`:

### Archived Files
- `ci-cd-pipeline-original.yml` - Original comprehensive pipeline (reference)
- `deploy.yml` - Deployment-specific workflow
- `automated-testing.yml` - Basic testing workflow
- `production-deployment.yml` - Production deployment workflow
- `submodule-integration.yml` - Submodule integration testing
- `pr-validation.yml` - Pull request validation
- `claude.yml` - Claude AI integration workflow
- `claude-code-review.yml` - AI-powered code review
- `ai-enhanced-ci.yml` - AI-enhanced continuous integration
- `ai-deployment.yml` - AI-assisted deployment
- `staging-deploy.yml` - Staging deployment workflow
- `production-deploy.yml` - Production deployment workflow
- `ai-security.yml` - AI-powered security scanning

### Consolidation Benefits

1. **Single Source of Truth**: One comprehensive workflow vs. 13+ fragmented files
2. **Reduced Maintenance**: Eliminate conflicts and duplication across workflows
3. **Clear Dependencies**: Logical stage progression with explicit requirements
4. **Resource Optimization**: Better caching and parallel/sequential execution
5. **Improved Observability**: Centralized reporting and artifact collection

## Workflow Integration Points

### Test Infrastructure Integration
- Containerized testing environments (`docker-compose.test.yml`, `docker-compose.integration.yml`)
- Performance regression testing with statistical baseline comparison
- Comprehensive E2E authentication and frontend-backend integration
- Security scanning and compliance validation

### External Dependencies
- TimescaleDB and Redis services for integration testing
- Docker registry (GitHub Container Registry) for image storage
- Kubernetes for staging deployment
- Playwright for browser compatibility testing

### Artifacts and Reporting
- JUnit XML test results for all stages
- Coverage reports (XML and HTML)
- Performance regression reports with baselines
- Security audit results
- Docker image build validation
- Comprehensive test summary with stage results

## Usage

### Standard Development Flow
```bash
# Triggers full pipeline on main/develop push
git push origin main

# Triggers core testing on PR
git push origin feature-branch
gh pr create --title "Feature X"
```

### Advanced Testing Triggers
```bash
# Trigger performance testing on PR
gh pr edit --add-label "performance"

# Trigger frontend testing on PR
gh pr edit --add-label "frontend"
```

### Manual Workflow Dispatch
The workflow supports manual triggering through GitHub Actions UI for testing and validation purposes.

## Monitoring and Debugging

### Key Metrics
- **Total Pipeline Duration**: Target < 45 minutes
- **Core Testing Duration**: Target < 20 minutes
- **E2E Testing Duration**: Target < 15 minutes
- **Success Rate**: Target > 95% for main branch

### Common Issues and Solutions

1. **Database Connection Failures**
   - Check service health checks in workflow
   - Verify migration scripts are current

2. **Container Build Failures**
   - Check Docker layer caching
   - Verify base image availability

3. **Performance Regression Failures**
   - Review baseline files in `tests/performance/baselines/`
   - Check API availability for performance testing

4. **E2E Test Failures**
   - Review container logs in test artifacts
   - Check service startup timing and health checks

### Artifact Access
All test results, reports, and logs are available as workflow artifacts:
- Download from GitHub Actions run page
- Automated retention: 90 days
- Includes comprehensive test summary and stage-specific results

---

This consolidated workflow provides comprehensive testing coverage while maintaining efficiency and clarity for the FXML4 development pipeline.
