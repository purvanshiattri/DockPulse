pipeline {
    agent any

    stages {

        // Get latest code from GitHub
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        // Build Docker image
        stage('Build Docker Image') {
            steps {
                sh 'docker build -t dockpulse .'
            }
        }

        // Stop old container and run new one
        stage('Deploy Container') {
            steps {
                sh 'docker stop dockpulse-container || true'
                sh 'docker rm dockpulse-container || true'

                sh '''
                docker run -d \
                -p 5001:5000 \
                --name dockpulse-container \
                -v /var/run/docker.sock:/var/run/docker.sock \
                dockpulse
                '''
            }
        }
    }

    post {
        success {
            echo 'DockPulse deployed successfully!'
        }

        failure {
            echo 'Pipeline failed!'
        }
    }
}