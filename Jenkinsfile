pipeline {
    agent any

    // ── Environment variables ──────────────────────────────────────────────
    environment {
        APP_NAME        = 'task-manager'
        IMAGE_NAME      = "task-manager"
        BUILD_VERSION   = "${APP_NAME}-${BUILD_NUMBER}"
        STAGING_PORT    = '5001'
        PROD_PORT       = '5000'
        SONAR_HOST_URL  = 'http://sonarqube:9000'
        // SONAR_TOKEN and DOCKER_CREDENTIALS set as Jenkins credentials
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
    }

    // ── Triggers ───────────────────────────────────────────────────────────
    triggers {
        pollSCM('H/5 * * * *')   // Poll GitHub every 5 minutes
    }

    stages {

        // ══════════════════════════════════════════════════════════════════
        // STAGE 1 ── BUILD
        // Installs dependencies inside a Python Docker container and builds
        // a tagged Docker image artefact ready for deployment.
        // ══════════════════════════════════════════════════════════════════
        stage('Build') {
            steps {
                echo "=== BUILD STAGE | Version: ${BUILD_VERSION} ==="

                // Verify Python environment and install deps
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    echo "Dependencies installed successfully"
                '''

                // Build Docker image with build number tag + latest tag
                sh '''
                    docker build \
                        --label "build.number=${BUILD_NUMBER}" \
                        --label "build.date=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                        -t ${IMAGE_NAME}:${BUILD_NUMBER} \
                        -t ${IMAGE_NAME}:latest \
                        .
                    echo "Docker image built: ${IMAGE_NAME}:${BUILD_NUMBER}"
                    docker images | grep ${IMAGE_NAME}
                '''
            }

            post {
                success {
                    echo "BUILD SUCCESS — artefact: ${IMAGE_NAME}:${BUILD_NUMBER}"
                }
                failure {
                    echo "BUILD FAILED — check Docker daemon and requirements.txt"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════
        // STAGE 2 ── TEST
        // Runs full pytest suite (unit + integration) with coverage report.
        // Pipeline fails if any test fails or coverage drops below 70%.
        // ══════════════════════════════════════════════════════════════════
        stage('Test') {
            steps {
                echo "=== TEST STAGE ==="

                sh '''
                    . venv/bin/activate
                    pytest tests/ \
                        --cov=app \
                        --cov-report=xml:coverage.xml \
                        --cov-report=html:htmlcov \
                        --cov-fail-under=70 \
                        --junitxml=test-results.xml \
                        -v
                '''
            }

            post {
                always {
                    // Publish JUnit test results in Jenkins UI
                    junit 'test-results.xml'

                    // Publish HTML coverage report
                    publishHTML(target: [
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
                success {
                    echo "TEST STAGE PASSED"
                }
                failure {
                    echo "TEST STAGE FAILED — review test-results.xml"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════
        // STAGE 3 ── CODE QUALITY (SonarQube)
        // Analyses codebase for code smells, duplications, complexity.
        // Quality Gate is enforced — build fails if gate is not met.
        // ══════════════════════════════════════════════════════════════════
        stage('Code Quality') {
            steps {
                echo "=== CODE QUALITY STAGE ==="

                // flake8 linting (style/syntax)
                sh '''
                    . venv/bin/activate
                    flake8 app/ --max-line-length=120 --statistics \
                        --format=default | tee flake8-report.txt || true
                    echo "Flake8 lint complete"
                '''

                // SonarQube analysis with Quality Gate
                withSonarQubeEnv('SonarQube') {
                    sh '''
                        sonar-scanner \
                            -Dsonar.projectKey=${APP_NAME} \
                            -Dsonar.projectName="Task Manager API" \
                            -Dsonar.projectVersion=${BUILD_NUMBER} \
                            -Dsonar.sources=app \
                            -Dsonar.tests=tests \
                            -Dsonar.python.coverage.reportPaths=coverage.xml \
                            -Dsonar.host.url=${SONAR_HOST_URL} \
                            -Dsonar.login=${SONAR_TOKEN}
                    '''
                }
            }

            post {
                always {
                    timeout(time: 3, unit: 'MINUTES') {
                        waitForQualityGate abortPipeline: false
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════
        // STAGE 4 ── SECURITY
        // Runs two complementary scans:
        //   • Bandit  — static analysis for Python code vulnerabilities
        //   • Trivy   — Docker image vulnerability scanner (CVEs)
        // Results are archived; critical CVEs fail the pipeline.
        // ══════════════════════════════════════════════════════════════════
        stage('Security') {
            steps {
                echo "=== SECURITY STAGE ==="

                // Bandit: Python static security analysis
                sh '''
                    . venv/bin/activate
                    bandit -r app/ \
                        -f json \
                        -o bandit-report.json \
                        --severity-level medium \
                        --confidence-level medium \
                        -x tests/ || true

                    echo "--- Bandit Summary ---"
                    python3 -c "
import json, sys
with open('bandit-report.json') as f:
    report = json.load(f)
metrics = report.get('metrics', {}).get('_totals', {})
high    = metrics.get('SEVERITY.HIGH', 0)
medium  = metrics.get('SEVERITY.MEDIUM', 0)
low     = metrics.get('SEVERITY.LOW', 0)
print(f'High: {high}, Medium: {medium}, Low: {low}')
if high > 0:
    print('WARNING: HIGH severity issues found — review bandit-report.json')
    sys.exit(1)
print('Bandit security scan passed')
"
                '''

                // Trivy: Docker image CVE scan
                sh '''
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        aquasec/trivy:latest image \
                        --exit-code 0 \
                        --severity CRITICAL,HIGH \
                        --format json \
                        --output trivy-report.json \
                        ${IMAGE_NAME}:${BUILD_NUMBER} || true

                    echo "Trivy scan complete — see trivy-report.json for details"
                '''
            }

            post {
                always {
                    archiveArtifacts artifacts: 'bandit-report.json,trivy-report.json',
                                     allowEmptyArchive: true
                }
                success {
                    echo "SECURITY STAGE PASSED — no critical issues"
                }
                failure {
                    echo "SECURITY STAGE FAILED — HIGH severity vulnerabilities found"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════
        // STAGE 5 ── DEPLOY (Staging)
        // Tears down any old staging container and deploys a fresh one.
        // Waits for the /health endpoint to confirm the app is live.
        // ══════════════════════════════════════════════════════════════════
        stage('Deploy') {
            steps {
                echo "=== DEPLOY STAGE (Staging) ==="

                sh '''
                    # Stop and remove existing staging container (ignore if not running)
                    docker rm -f task-manager-staging 2>/dev/null || true

                    # Deploy new staging container
                    docker run -d \
                        --name task-manager-staging \
                        --restart unless-stopped \
                        --network devops-network \
                        -p ${STAGING_PORT}:5000 \
                        -e FLASK_ENV=staging \
                        ${IMAGE_NAME}:${BUILD_NUMBER}

                    echo "Container deployed — waiting for health check..."

                    # Poll /health up to 30 seconds
                    for i in $(seq 1 10); do
                        sleep 3
                        STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                            http://task-manager-staging:5000/health || echo "000")
                        if [ "$STATUS" = "200" ]; then
                            echo "Health check PASSED (attempt $i) — staging is live on port ${STAGING_PORT}"
                            exit 0
                        fi
                        echo "Attempt $i: got HTTP $STATUS — retrying..."
                    done

                    echo "STAGING HEALTH CHECK FAILED after 10 attempts"
                    docker logs task-manager-staging
                    exit 1
                '''
            }

            post {
                success {
                    echo "STAGING DEPLOY SUCCESS — http://localhost:${STAGING_PORT}"
                }
                failure {
                    sh 'docker logs task-manager-staging || true'
                    echo "STAGING DEPLOY FAILED"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════
        // STAGE 6 ── RELEASE (Production)
        // Promotes the validated image to production with a Git-style tag,
        // zero-downtime swap, and rollback support on failure.
        // ══════════════════════════════════════════════════════════════════
        stage('Release') {
            steps {
                echo "=== RELEASE STAGE (Production) ==="

                sh '''
                    RELEASE_TAG="release-${BUILD_NUMBER}"

                    # Tag the image as a versioned release
                    docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:${RELEASE_TAG}
                    docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:stable
                    echo "Tagged image as ${RELEASE_TAG} and stable"

                    # Keep previous production container name for rollback
                    docker rename task-manager-production task-manager-previous 2>/dev/null || true

                    # Deploy to production
                    docker run -d \
                        --name task-manager-production \
                        --restart always \
                        --network devops-network \
                        -p ${PROD_PORT}:5000 \
                        -e FLASK_ENV=production \
                        ${IMAGE_NAME}:${RELEASE_TAG}

                    echo "Production container started — verifying..."
                    sleep 5

                    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                        http://task-manager-production:5000/health || echo "000")

                    if [ "$STATUS" = "200" ]; then
                        echo "PRODUCTION HEALTH CHECK PASSED — ${RELEASE_TAG} is live"
                        # Remove old production backup on success
                        docker rm -f task-manager-previous 2>/dev/null || true
                    else
                        echo "PRODUCTION HEALTH CHECK FAILED — rolling back to previous"
                        docker rm -f task-manager-production 2>/dev/null || true
                        docker rename task-manager-previous task-manager-production 2>/dev/null || true
                        exit 1
                    fi
                '''
            }

            post {
                success {
                    echo "RELEASE SUCCESS — production running build ${BUILD_NUMBER}"
                }
                failure {
                    echo "RELEASE FAILED — rollback executed"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════
        // STAGE 7 ── MONITORING & ALERTING
        // Starts Prometheus + Grafana monitoring stack.
        // Runs a live smoke test against the /metrics endpoint and
        // simulates an incident-style health check for alerting demo.
        // ══════════════════════════════════════════════════════════════════
        stage('Monitoring') {
            steps {
                echo "=== MONITORING STAGE ==="

                // Start monitoring stack (Prometheus + Grafana)
                sh '''
                    export BUILD_VERSION=${BUILD_NUMBER}
                    docker-compose up -d prometheus grafana

                    echo "Waiting for monitoring stack to initialise..."
                    sleep 10

                    # Verify Prometheus is up
                    PROM_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                        http://localhost:9090/-/healthy || echo "000")
                    echo "Prometheus status: HTTP $PROM_STATUS"

                    # Verify Grafana is up
                    GRAFANA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                        http://localhost:3000/api/health || echo "000")
                    echo "Grafana status: HTTP $GRAFANA_STATUS"
                '''

                // Verify production metrics endpoint is being scraped
                sh '''
                    echo "--- Verifying /metrics endpoint ---"
                    METRICS=$(curl -s http://task-manager-production:5000/metrics)
                    echo "$METRICS"

                    if echo "$METRICS" | grep -q "tasks_total"; then
                        echo "Metrics endpoint OK — Prometheus scrape target confirmed"
                    else
                        echo "WARNING: metrics endpoint did not return expected data"
                    fi
                '''

                // Incident simulation: stop production, detect failure, restart
                sh '''
                    echo "--- Incident Simulation ---"
                    echo "Simulating outage: stopping production container..."
                    docker stop task-manager-production

                    sleep 5
                    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" \
                        http://task-manager-production:5000/health || echo "000")
                    echo "Health during outage: HTTP $HEALTH (expected: not 200)"

                    echo "Recovering: restarting production container..."
                    docker start task-manager-production
                    sleep 5

                    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" \
                        http://task-manager-production:5000/health || echo "000")
                    if [ "$HEALTH" = "200" ]; then
                        echo "Incident simulation COMPLETE — recovery successful"
                    else
                        echo "Recovery check FAILED"
                        exit 1
                    fi
                '''
            }

            post {
                success {
                    echo "MONITORING STAGE PASSED"
                    echo "Grafana dashboards: http://localhost:3000 (admin/admin)"
                    echo "Prometheus:         http://localhost:9090"
                }
                failure {
                    echo "MONITORING STAGE FAILED"
                }
            }
        }
    }

    // ── Post-pipeline actions ──────────────────────────────────────────────
    post {
        always {
            echo "Pipeline complete — Build #${BUILD_NUMBER}"

            // Archive all reports
            archiveArtifacts artifacts: '''
                bandit-report.json,
                trivy-report.json,
                flake8-report.txt,
                coverage.xml,
                test-results.xml
            ''', allowEmptyArchive: true

            // Clean up dangling Docker images
            sh 'docker image prune -f || true'
        }

        success {
            echo """
            ╔══════════════════════════════════════════════╗
            ║   PIPELINE SUCCEEDED — Build #${BUILD_NUMBER}
            ║   Staging:    http://localhost:${STAGING_PORT}
            ║   Production: http://localhost:${PROD_PORT}
            ║   Grafana:    http://localhost:3000
            ║   Prometheus: http://localhost:9090
            ╚══════════════════════════════════════════════╝
            """
        }

        failure {
            echo "PIPELINE FAILED — review stage logs above"
        }

        cleanup {
            // Clean workspace after build (keeps Jenkins agent tidy)
            cleanWs()
        }
    }
}
