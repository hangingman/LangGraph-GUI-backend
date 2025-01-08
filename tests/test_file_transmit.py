import pytest
from fastapi.testclient import TestClient
from FileTransmit import file_router
import os
import shutil

@pytest.fixture
def client():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(file_router)
    return TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists('./workspace/'):
        shutil.rmtree('./workspace/')
    yield
    if os.path.exists('./workspace/'):
        shutil.rmtree('./workspace/')

def test_upload_and_download(client):
    files = [('files', ('test.txt', b'hello world'))]
    response = client.post('/upload/testuser', files=files)
    assert response.status_code == 200
    
    response = client.get('/download/testuser')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/zip'
    assert 'attachment; filename=testuser_workspace.zip' in response.headers['content-disposition']

def test_graph_operations(client):
    graph_data = {
        'nodes': [
            {'name': 'node1', 'nexts': []},
            {'name': 'node2', 'nexts': []}
        ]
    }
    response = client.post('/graph/testuser', json=graph_data)
    assert response.status_code == 200
    graph_uuid = response.json()['uuid']
    
    response = client.get(f'/graph/testuser/{graph_uuid}')
    assert response.status_code == 200
    assert len(response.json()['nodes']) == 2
    
    #response = client.get('/graphs/testuser')
    #assert response.status_code == 200
    #assert graph_uuid == response.json()['uuid']

def test_clean_cache(client):
    files = [('files', ('test.txt', b'hello world'))]
    client.post('/upload/testuser', files=files)
    
    response = client.post('/clean-cache/testuser')
    assert response.status_code == 200
    
    response = client.get('/download/testuser')
    assert response.status_code == 200

