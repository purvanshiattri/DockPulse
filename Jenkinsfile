pipeline {
    agent any

    options {
        // Prevent multiple builds running simultaneously on the same agent
        disableConcurrentBuilds()
        // Print build timestamps in the log
        timestamps()
    }

    environment {
        REGISTRY = 'docker.io'
        IMAGE_NAME = 'dockpulse-dashboard'
        KUBECONFIG_CREDENTIAL_ID = 'kubeconfig-prod'
    }

    stages {
        stage('1. Checkout Code') {
            steps {
                echo 'Checking out revision from source repository...'
                checkout scm
            }
        }

        stage('2. Environment & Dependencies') {
            steps {
                echo 'Setting up Python virtual environment and installing modules...'
                // Install requirements in user environment or virtualenv
                sh '''
                    python -m venv venv
                    . venv/bin/activate || ./venv/Scripts/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('3. Lint & Code Quality') {
            steps {
                echo 'Performing static code compile validation...'
                // Compiles all python files in the directory to check for syntax issues
                sh '''
                    . venv/bin/activate || ./venv/Scripts/activate
                    python -m compileall -q .
                '''
            }
        }

        stage('4. Docker Build') {
            steps {
                echo "Building Docker container image: ${IMAGE_NAME}:${BUILD_NUMBER}..."
                sh "docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} ."
            }
        }

        stage('5. Docker Tag & Push') {
            steps {
                echo 'Pushing image layers to Docker Registry...'
                // In production, we would authenticate and push using withCredentials block:
                // withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                //     sh "docker login -u $USER -p $PASS"
                //     sh "docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${REGISTRY}/${USER}/${IMAGE_NAME}:${BUILD_NUMBER}"
                //     sh "docker push ${REGISTRY}/${USER}/${IMAGE_NAME}:${BUILD_NUMBER}"
                // }
                sh "docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest"
                echo 'Docker tag latest created successfully (local registry simulated).'
            }
        }

        stage('6. Deploy to Kubernetes') {
            steps {
                echo 'Deploying resources to Kubernetes cluster...'
                // In production, we select the correct context using kubeconfig credentials:
                // configFileProvider([configFile(fileId: KUBECONFIG_CREDENTIAL_ID, targetLocation: 'kubeconfig')]) {
                //     sh "KUBECONFIG=kubeconfig kubectl apply -f k8s/"
                // }
                sh "kubectl apply -f k8s/deployment.yaml"
                sh "kubectl apply -f k8s/service.yaml"
                echo 'Deployment configurations applied to Pod Replication Controllers.'
            }
        }
    }

    post {
        success {
            echo '==================================================='
            echo '  CI/CD PIPELINE EXECUTION COMPLETED SUCCESSFULLY  '
            echo '==================================================='
        }
        failure {
            echo '==================================================='
            echo '  CI/CD PIPELINE EXECUTION FAILED! CHECK LOGS.     '
            echo '==================================================='
        }
    }
}
