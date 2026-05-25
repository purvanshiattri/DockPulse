pipeline {
    agent any

    options {
        // Prevent concurrent builds on the same agent workspace to avoid conflicts
        disableConcurrentBuilds()
        // Print build timestamps in the console logs for easier debugging
        timestamps()
    }

    stages {
        // STAGE 1: Pull the latest source code from the Git repository (GitHub)
        stage('1. Checkout Code') {
            steps {
                echo 'Checking out revision from source repository...'
                checkout scm
            }
        }

        // STAGE 2: Build the Docker image from our Dockerfile
        // --------------------------------------------------------------------------
        // ENVIRONMENT-AGNOSTIC BUILD PRINCIPLE:
        // We do not need Python or pip installed on the Jenkins container agent itself.
        // The Dockerfile handles copying requirements.txt and running 'pip install' 
        // inside an isolated, containerized environment during the build process.
        // This keeps the Jenkins host clean and avoids version conflicts between builds.
        // --------------------------------------------------------------------------
        stage('2. Docker Build') {
            steps {
                echo 'Building the DockPulse container image...'
                sh 'docker build -t dockpulse .'
            }
        }
    }

    post {
        success {
            echo '==================================================='
            echo '  CI PIPELINE COMPLETED SUCCESSFULLY: IMAGE BUILT  '
            echo '==================================================='
        }
        failure {
            echo '==================================================='
            echo '  CI PIPELINE FAILED: CHECK LOGS                   '
            echo '==================================================='
        }
    }
}
