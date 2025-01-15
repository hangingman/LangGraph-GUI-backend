import pytest
from fastapi.testclient import TestClient
from FileTransmit import file_router
import os
import shutil
import json
import pathlib

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

def test_save_example_graph(client):
    file = pathlib.Path("tests/test_data/example.json")
    with open(file) as f:
        example_graph_data = json.load(f)

    response = client.post('/graph/testuser', json=example_graph_data)
    assert response.status_code == 200
    graph_uuid = response.json()['uuid']
    
    response = client.get(f'/graph/testuser/{graph_uuid}')
    assert response.status_code == 200
    
    saved_nodes = response.json()['nodes']
    assert len(saved_nodes) == len(example_graph_data['nodes'])
    
    for saved_node, original_node in zip(saved_nodes, example_graph_data['nodes']):
        assert saved_node['name'] == original_node['name']
        assert saved_node['type'] == original_node['type']
        assert saved_node['description'] == original_node['description']

def test_clean_cache(client):
    files = [('files', ('test.txt', b'hello world'))]
    client.post('/upload/testuser', files=files)
    
    response = client.post('/clean-cache/testuser')
    assert response.status_code == 200
    
    response = client.get('/download/testuser')
    assert response.status_code == 200

