pipeline {
    agent {
        label 'docker'
    }
    stages {
        stage ('Docker') {
            agent {
                dockerfile {
                    // Required to be root to create vcan interfaces
                    args '-e HOME=/tmp -e BUILD_CONTEXT=ci --cap-add=NET_ADMIN -u 0:0'
                    additionalBuildArgs '--target build-tests'
                    reuseNode true
                }
            }
            stages {
                stage('Setup vcan'){
                    steps {
                        sh '''
                        ip link add dev vcan0 type vcan || true
                        ip link set up vcan0
                        ip link add dev vcan1 type vcan || true
                        ip link set up vcan1
                        ip link add dev vcan2 type vcan || true
                        ip link set up vcan2
                        ip link add dev vcan3 type vcan || true
                        ip link set up vcan3
                        ip link add dev vcan4 type vcan || true
                        ip link set up vcan4
                        '''
                    }
                }
                stage ('Create venvs') {
                    parallel{
                        stage ('Python 3.11') {
                            steps {
                                sh 'python3.11 -m venv venv-3.11 && VENV_DIR=venv3.11 scripts/activate-venv.sh'
                            }
                        }
                        stage ('Python 3.10') {
                            steps {
                                sh 'python3.10 -m venv venv-3.10 && VENV_DIR=venv3.10 scripts/activate-venv.sh'
                            }
                        }
                        stage ('Python 3.9') {
                            steps {
                                sh 'python3.9 -m venv venv-3.9 && VENV_DIR=venv3.9 scripts/activate-venv.sh'
                            }
                        }
                        stage ('Python 3.8') {
                            steps {
                                sh 'python3.8 -m venv venv-3.8 && VENV_DIR=venv3.8 scripts/activate-venv.sh'
                            }
                        }
                        stage ('Python 3.7') {
                            steps {
                                sh 'python3.7 -m venv venv-3.7 && VENV_DIR=venv3.7 scripts/activate-venv.sh'
                            }
                        }
                    }
                }
                stage('Testing'){
                    parallel{
                        
                        stage ('Python 3.11') {
                            steps {
                                sh '''
                                VENV_DIR=venv-3.11 scripts/with-venv.sh scripts/check-python-version.sh 3.11
                                VENV_DIR=venv-3.11 COVERAGE_SUFFIX=3.11 UNITTEST_VCAN=vcan0 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.10') {
                            steps {
                                sh '''
                                VENV_DIR=venv-3.10 scripts/with-venv.sh scripts/check-python-version.sh 3.10
                                VENV_DIR=venv-3.10 COVERAGE_SUFFIX=3.10 UNITTEST_VCAN=vcan1 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.9') {
                            steps {
                                sh '''
                                VENV_DIR=venv-3.9 scripts/with-venv.sh scripts/check-python-version.sh 3.9
                                VENV_DIR=venv-3.9 COVERAGE_SUFFIX=3.9 UNITTEST_VCAN=vcan2 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.8') {
                            steps {
                                sh '''
                                VENV_DIR=venv-3.8 scripts/with-venv.sh scripts/check-python-version.sh 3.8
                                VENV_DIR=venv-3.8 COVERAGE_SUFFIX=3.8 UNITTEST_VCAN=vcan3 scripts/with-venv.sh scripts/runtests.sh 
                                '''
                            }
                        }
                        stage ('Python 3.7') {
                            steps {
                                sh '''
                                VENV_DIR=venv-3.7 scripts/with-venv.sh scripts/check-python-version.sh 3.7
                                VENV_DIR=venv-3.7 COVERAGE_SUFFIX=3.7 UNITTEST_VCAN=vcan4 scripts/with-venv.sh scripts/runtests.sh 
                                '''
                            }
                        }
                    }
                }
                stage("Doc"){
                    steps {
                        sh '''
                        VENV_DIR=venv-3.11 scripts/with-venv.sh pip3 install -r doc/requirements.txt
                        VENV_DIR=venv-3.11 scripts/with-venv.sh make -C doc html
                        '''
                    }
                }
            }
        }
    }
}
