# FileTransmit.py

from typing import List
import os
import zipfile
import io
from datetime import datetime
import json
import uuid
from simple_graph_sqlite import database as sg_db

from fastapi import HTTPException, BackgroundTasks
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.responses import StreamingResponse
from fastapi.responses import Response


# Create a router instance
file_router = APIRouter()

# Utility function to get or create a user's workspace directory
def get_or_create_workspace(username: str) -> str:
    """
    Ensures the workspace directory for a given username exists.
    Creates the directory and initializes SQLite database if it doesn't exist.
    """
    workspace_path = os.path.join('./workspace/', username)
    if not os.path.exists(workspace_path):
        os.makedirs(workspace_path)
        print(f"Created workspace for {username} at {workspace_path}")
        
        # Initialize SQLite database
        db_path = os.path.join(workspace_path, 'graphs.db')
        sg_db.initialize(db_path)
        
    return workspace_path

def get_db_path(username: str) -> str:
    """Get SQLite database file path for the user"""
    workspace_path = get_or_create_workspace(username)
    return os.path.join(workspace_path, 'graphs.db')


@file_router.get('/download/{username}')
async def download_workspace(username: str):
    try:
        user_workspace = get_or_create_workspace(username)

        # Create a zip file from the user's workspace directory
        zip_filename = f'{username}_workspace.zip'
        zip_buffer = io.BytesIO()  # in-memory buffer to hold the zip file

        # Create a ZipFile object in write mode
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Walk through the workspace directory and add files to the zip
            for root, dirs, files in os.walk(user_workspace):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, user_workspace)  # Store files relative to the workspace
                    zip_file.write(file_path, arcname)

        # Seek to the beginning of the buffer before sending it
        zip_buffer.seek(0)

        # Return the zip file as a Response, without triggering stat checks
        return Response(
            zip_buffer.read(),  # Read the content of the BytesIO object
            media_type="application/zip",  # Set the media type to zip file
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
    
    except Exception as e:
        print(f"Error creating zip: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create zip file: {str(e)}")

# Route to handle file uploads with username
@file_router.post('/upload/{username}')
async def upload_file(username: str, files: List[UploadFile] = File(...)):
    user_workspace = get_or_create_workspace(username)

    if not files:
        raise HTTPException(status_code=400, detail="No files selected for uploading")

    # Save each uploaded file to the user's workspace
    for file in files:
        file_path = os.path.join(user_workspace, file.filename)
        with open(file_path, 'wb') as f:
            f.write(await file.read())
        print(f"Uploaded file: {file.filename} to {user_workspace}")
    
    return JSONResponse(content={"message": "Files successfully uploaded"}, status_code=200)

@file_router.post('/graph/{username}')
async def post_graph(username: str, graph_data: dict):
    """
    Save a new graph to the database
    Returns the UUID of the saved graph
    """
    try:
        db_path = get_db_path(username)
        
        # Generate UUID for new graph
        graph_uuid = str(uuid.uuid4())
        
        # Save nodes
        nodes = graph_data.get('nodes', [])
        node_ids = [str(uuid.uuid4()) for _ in nodes]
        node_bodies = [{
            **node,
            'graph_uuid': graph_uuid,
            'node_id': node_ids[i]
        } for i, node in enumerate(nodes)]
        
        # Save edges
        edges = []
        for i, node in enumerate(nodes):
            for next_id in node.get('nexts', []):
                edges.append({
                    'source': node_ids[i],
                    'target': next_id,
                    'properties': {}
                })
        
        # Save to database
        sg_db.atomic(db_path, sg_db.add_nodes(node_bodies, node_ids))
        if edges:
            sources = [e['source'] for e in edges]
            targets = [e['target'] for e in edges]
            properties = [e['properties'] for e in edges]
            sg_db.atomic(db_path, sg_db.connect_many_nodes(sources, targets, properties))
            
        return JSONResponse(content={"uuid": graph_uuid}, status_code=200)
        
    except Exception as e:
        print(f"Error saving graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save graph: {str(e)}")

@file_router.get('/graph/{username}/{graph_uuid}')
async def get_graph_by_uuid(username: str, graph_uuid: str):
    """
    Retrieve a graph by its UUID
    Returns the graph data in JSON format
    """
    try:
        db_path = get_db_path(username)
        
        # Find nodes for this graph
        clause = sg_db._generate_clause('graph_uuid')
        nodes = sg_db.atomic(db_path, sg_db.find_nodes([clause], (graph_uuid,)))
        
        # Build node mapping
        node_map = {n['node_id']: n for n in nodes}
        
        # Find edges and build connections
        for node in nodes:
            connections = sg_db.atomic(db_path, sg_db.get_connections(node['node_id']))
            node['nexts'] = [edge[1] for edge in connections]
            
        # Remove internal fields
        for node in nodes:
            node.pop('graph_uuid', None)
            node.pop('node_id', None)
            
        return JSONResponse(content={"nodes": nodes}, status_code=200)
        
    except Exception as e:
        print(f"Error retrieving graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve graph: {str(e)}")

@file_router.get('/graphs/{username}')
async def list_graphs(username: str):
    """
    List all graph UUIDs for a user
    Returns a list of UUIDs
    """
    try:
        db_path = get_db_path(username)
        
        # Get unique graph UUIDs
        clause = sg_db._generate_clause('graph_uuid', tree=True)
        graphs = sg_db.atomic(db_path, sg_db.find_nodes(
            [clause],
            ('%',),
            tree_query=True,
            key='graph_uuid'
        ))
        
        # Extract unique UUIDs
        uuids = list(set(g['graph_uuid'] for g in graphs))
        
        return JSONResponse(content={"uuids": uuids}, status_code=200)
        
    except Exception as e:
        print(f"Error listing graphs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list graphs: {str(e)}")

# Route to handle cleaning the user's workspace
@file_router.post('/clean-cache/{username}')
async def clean_cache(username: str):
    try:
        # Get or create the user's workspace
        user_workspace = get_or_create_workspace(username)

        # Delete all files in the user's workspace
        for root, dirs, files in os.walk(user_workspace):
            for file in files:
                file_path = os.path.join(root, file)
                os.remove(file_path)
                print(f"Deleted file: {file_path}")

        return JSONResponse(content={"message": "Workspace successfully cleaned"}, status_code=200)

    except Exception as e:
        print(f"Error cleaning workspace: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clean workspace: {str(e)}")
