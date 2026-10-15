pipeline {
    agent any

    environment {
        PYTHON_EXE = 'C:/Users/Purvanshi Attri/AppData/Local/Programs/Python/Python313/python.exe'
        DOCKER_EXE = 'C:/Users/Purvanshi Attri/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'

        AWS_DEFAULT_REGION = 'us-east-1'
        IMAGE_NAME = 'dockpulse'
        IMAGE_TAG = 'latest'
        ECR_REGISTRY = ''
    }

    stages {
        stage('Checkout Code') {
            steps {
                bat '''
                if not exist .git (
                    git clone https://github.com/purvanshiattri/DockPulse.git .
                    if errorlevel 1 exit /b 1
                ) else (
                    git pull origin main
                    if errorlevel 1 exit /b 1
                )
                '''
            }
        }

        stage('Run Unit Tests') {
            steps {
                bat '"%PYTHON_EXE%" --version'
                bat '"%PYTHON_EXE%" -m unittest discover -s tests -v'
            }
        }

        stage('Build Docker Image') {
            steps {
                bat '"%DOCKER_EXE%" version'
                bat '"%DOCKER_EXE%" build -t dockpulse:latest -t devopsproj-dockpulse:latest .'
            }
        }

        stage('Publish to Registry') {
            when {
                expression {
                    return env.ECR_REGISTRY?.trim()
                }
            }
            steps {
                bat '"%DOCKER_EXE%" tag dockpulse:latest "%ECR_REGISTRY%/dockpulse:%IMAGE_TAG%"'
                bat '"%DOCKER_EXE%" push "%ECR_REGISTRY%/dockpulse:%IMAGE_TAG%"'
            }
        }

        stage('Deploy Local Container') {
            steps {
                bat '''
                "%DOCKER_EXE%" rm -f dockpulse-container 2>nul
                "%DOCKER_EXE%" run -d -p 5001:5000 --name dockpulse-container -v /var/run/docker.sock:/var/run/docker.sock dockpulse:latest
                if errorlevel 1 exit /b 1
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                bat '''
                "%DOCKER_EXE%" ps --filter "name=dockpulse-container"
                "%DOCKER_EXE%" inspect --format="{{.State.Status}}" dockpulse-container
                '''
                echo 'DockPulse deployment verification commands completed.'
            }
        }

        stage('Pipeline Complete') {
            steps {
                echo 'All DockPulse CI/CD stages completed successfully.'
            }
        }
    }
}