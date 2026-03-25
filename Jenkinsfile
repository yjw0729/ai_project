// Jenkinsfile for API Test Automation
// Requires: Jenkins, Pipeline plugin, Python 3.x, Allure

pipeline {
    agent {
        docker {
            image 'python:3.12-slim'
            label 'docker'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
        }
    }

    environment {
        PYTHON_VERSION = '3.12'
        ALLURE_RESULTS = 'allure-results'
        ALLURE_REPORT = 'allure-report'
        PYTEST_ARGS = '-v --tb=short --alluredir=./allure-results'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '30'))
        timeout(time: 2, unit: 'HOURS')
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        choice(
            name: 'TEST_MARKER',
            choices: ['ci_cd', 'smoke', 'regression', 'P0', 'P1', 'P2', 'P3', 'all'],
            description: '选择要执行的测试标记'
        )
        booleanParam(
            name: 'RUN_PARALLEL',
            defaultValue: true,
            description: '是否并行执行测试'
        )
        booleanParam(
            name: 'GENERATE_REPORT',
            defaultValue: true,
            description: '是否生成 Allure 报告'
        )
        string(
            name: 'TEST_SUITE',
            defaultValue: '',
            description: '指定测试套件路径 (可选)'
        )
        string(
            name: 'TEST_TAGS',
            defaultValue: '',
            description: '额外的测试标签 (可选, 逗号分隔)'
        )
    }

    stages {
        stage('Initialize') {
            steps {
                script {
                    echo "========================================="
                    echo "API Test Automation Pipeline"
                    echo "========================================="
                    echo "Python Version: ${env.PYTHON_VERSION}"
                    echo "Test Marker: ${params.TEST_MARKER}"
                    echo "Run Parallel: ${params.RUN_PARALLEL}"
                    echo "========================================="
                }
            }
        }

        stage('Checkout') {
            steps {
                echo "Checking out source code..."
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    sh '''
                        python -m pip install --upgrade pip setuptools wheel
                        pip install -r requirements.txt || pip install -r test_requirements.txt 2>/dev/null || true
                        pip install pytest pytest-xdist pytest-allure allure-python-py2
                    '''
                }
            }
        }

        stage('Lint & Code Quality') {
            steps {
                script {
                    try {
                        sh '''
                            pip install flake8 black isort
                            flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || true
                            black --check . || true
                            isort --check-only --diff . || true
                        '''
                    } catch (Exception e) {
                        echo "Lint warnings found, continuing..."
                    }
                }
            }
        }

        stage('Smoke Tests') {
            when {
                anyOf {
                    expression { return params.TEST_MARKER == 'all' }
                    expression { return params.TEST_MARKER == 'smoke' }
                }
            }
            steps {
                script {
                    def pytestArgs = buildPytestArgs('smoke', params.RUN_PARALLEL)
                    sh "pytest ${pytestArgs}"
                }
            }
            post {
                always {
                    script {
                        archiveAllureResults('smoke')
                    }
                }
            }
        }

        stage('Regression Tests') {
            when {
                anyOf {
                    expression { return params.TEST_MARKER == 'all' }
                    expression { return params.TEST_MARKER == 'regression' }
                }
            }
            steps {
                script {
                    def pytestArgs = buildPytestArgs('regression', params.RUN_PARALLEL)
                    sh "pytest ${pytestArgs}"
                }
            }
            post {
                always {
                    script {
                        archiveAllureResults('regression')
                    }
                }
            }
        }

        stage('CI/CD Integration Tests') {
            when {
                anyOf {
                    expression { return params.TEST_MARKER == 'all' }
                    expression { return params.TEST_MARKER == 'ci_cd' }
                }
            }
            steps {
                script {
                    def pytestArgs = buildPytestArgs('ci_cd', params.RUN_PARALLEL)
                    sh "pytest ${pytestArgs}"
                }
            }
            post {
                always {
                    script {
                        archiveAllureResults('ci_cd')
                    }
                }
            }
        }

        stage('P0 Priority Tests') {
            when {
                anyOf {
                    expression { return params.TEST_MARKER == 'all' }
                    expression { return params.TEST_MARKER == 'P0' }
                }
            }
            steps {
                script {
                    def pytestArgs = buildPytestArgs('P0', params.RUN_PARALLEL)
                    sh "pytest ${pytestArgs}"
                }
            }
            post {
                always {
                    script {
                        archiveAllureResults('P0')
                    }
                }
            }
        }

        stage('P1 Priority Tests') {
            when {
                anyOf {
                    expression { return params.TEST_MARKER == 'all' }
                    expression { return params.TEST_MARKER == 'P1' }
                }
            }
            steps {
                script {
                    def pytestArgs = buildPytestArgs('P1', params.RUN_PARALLEL)
                    sh "pytest ${pytestArgs}"
                }
            }
            post {
                always {
                    script {
                        archiveAllureResults('P1')
                    }
                }
            }
        }

        stage('P2 Priority Tests') {
            when {
                anyOf {
                    expression { return params.TEST_MARKER == 'all' }
                    expression { return params.TEST_MARKER == 'P2' }
                }
            }
            steps {
                script {
                    def pytestArgs = buildPytestArgs('P2', params.RUN_PARALLEL)
                    sh "pytest ${pytestArgs}"
                }
            }
            post {
                always {
                    script {
                        archiveAllureResults('P2')
                    }
                }
            }
        }

        stage('P3 Priority Tests') {
            when {
                anyOf {
                    expression { return params.TEST_MARKER == 'all' }
                    expression { return params.TEST_MARKER == 'P3' }
                }
            }
            steps {
                script {
                    def pytestArgs = buildPytestArgs('P3', params.RUN_PARALLEL)
                    sh "pytest ${pytestArgs}"
                }
            }
            post {
                always {
                    script {
                        archiveAllureResults('P3')
                    }
                }
            }
        }

        stage('Generate Allure Report') {
            when {
                expression { return params.GENERATE_REPORT }
            }
            steps {
                script {
                    sh '''
                        if [ -d "allure-results" ] && [ "$(ls -A allure-results)" ]; then
                            allure generate allure-results -o allure-report --clean
                        else
                            echo "No test results found, skipping report generation"
                        fi
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'allure-report/**', allowEmptyArchive: true
                }
            }
        }

        stage('Publish Test Results') {
            steps {
                script {
                    allure includeProperties: false,
                         results: [[path: 'allure-results']],
                         report: 'allure-report'
                }
            }
        }

        stage('Send Notifications') {
            steps {
                script {
                    def status = currentBuild.result ?: 'SUCCESS'
                    def color = status == 'SUCCESS' ? 'green' : 'red'

                    // Send notification (configure based on your needs)
                    // slackSend(channel: '#tests', color: color, message: "Build ${env.BUILD_NUMBER} ${status}")
                    // emailext(subject: "Test Results: ${env.JOB_NAME} #${env.BUILD_NUMBER}", body: "Check console output at ${env.BUILD_URL}")

                    echo "Pipeline completed with status: ${status}"
                }
            }
        }
    }

    post {
        always {
            echo "========================================="
            echo "Pipeline Execution Summary"
            echo "========================================="
            echo "Build Number: ${env.BUILD_NUMBER}"
            echo "Build Status: ${currentBuild.result ?: 'SUCCESS'}"
            echo "Test Marker: ${params.TEST_MARKER}"
            echo "Allure Report: ${env.BUILD_URL}allure"
            echo "========================================="
        }
        success {
            echo "All tests passed!"
        }
        failure {
            echo "Some tests failed. Check the results."
        }
    }
}

/**
 * 构建 pytest 参数
 * @param marker 测试标记
 * @param parallel 是否并行
 * @return pytest 参数字符串
 */
def buildPytestArgs(String marker, boolean parallel) {
    def args = "-m \"${marker}\" -v --tb=short --alluredir=./allure-results"

    if (parallel) {
        args += " -n auto"
    }

    if (params.TEST_SUITE) {
        args += " ${params.TEST_SUITE}"
    } else {
        args += " tests/"
    }

    if (params.TEST_TAGS) {
        def tags = params.TEST_TAGS.split(',').collect { it.trim() }.join(' or ')
        args += " -m \"${marker} or (${tags})\""
    }

    return args
}

/**
 * 归档 Allure 测试结果
 * @param suffix 结果目录后缀
 */
def archiveAllureResults(String suffix) {
    def resultsDir = "allure-results-${suffix}"
    sh "mkdir -p ${resultsDir} && cp -r allure-results/* ${resultsDir}/ 2>/dev/null || true"
    archiveArtifacts artifacts: "${resultsDir}/**", allowEmptyArchive: true
}