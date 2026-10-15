pipeline {
    agent any

    environment {
        AWS_DEFAULT_REGION = env.AWS_REGION ?: 'us-east-1'
        IMAGE_NAME         = 'dockpulse'
        IMAGE_TAG          = env.BUILD_NUMBER ?: 'latest'
        ECR_REGISTRY       = env.AWS_ECR_REGISTRY ?: ''
        APP_PORT           = env.CONTAINER_PORT ?: '5000'
    }

    stages {

        // 1. Get latest code from version control
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        // 2. Automated Quality & Intelligence Unit Tests
        stage('Run Unit Tests') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'python -m unittest discover tests'
                    } else {
                        bat 'python -m unittest discover tests'
                    }
                }
            }
        }

        // 3. Build & Tag Container Image
        stage('Build Docker Image') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'docker build -t dockpulse:latest -t devopsproj-dockpulse:latest .'
                    } else {
                        bat 'docker build -t dockpulse:latest -t devopsproj-dockpulse:latest .'
                    }
                }
            }
        }

        // 4. Optional Publish to Container Registry for AWS Deployment
        stage('Publish to Registry') {
            when {
                expression { return env.ECR_REGISTRY != null && env.ECR_REGISTRY != '' }
            }
            steps {
                script {
                    echo "Publishing ${IMAGE_NAME}:${IMAGE_TAG} to ${ECR_REGISTRY}..."
                    if (isUnix()) {
                        sh "docker tag ${IMAGE_NAME}:latest ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                        sh "docker push ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                    } else {
                        bat "docker tag ${IMAGE_NAME}:latest ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                        bat "docker push ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                    }
                }
            }
        }

        // 4. Deploy or Recreate Container Instance
        stage('Deploy Container') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'docker stop dockpulse-container || true'
                        sh 'docker rm dockpulse-container || true'
                        sh '''
                        docker run -d \
                          -p 5001:5000 \
                          --name dockpulse-container \
                          -v /var/run/docker.sock:/var/run/docker.sock \
                          dockpulse:latest
                        '''
                    } else {
                        bat '''
                        docker stop dockpulse-container 2>nul || exit 0
                        docker rm dockpulse-container 2>nul || exit 0
                        docker run -d -p 5001:5000 --name dockpulse-container -v /var/run/docker.sock:/var/run/docker.sock dockpulse:latest
                        '''
                    }
                }
            }
        }
    }

    post {
        success {
            echo 'DockPulse CI/CD Pipeline executed successfully! Platform is healthy.'
        }

        failure {
            echo 'Pipeline failed! Check stage console output for debugging diagnostics.'
        }
    }
}