"""
This file contains the shared Pydantic models for the agent.
"""
from pydantic import BaseModel

class TreeNode(BaseModel):
    name: str
    path: str
    type: str
    sha: str
    url: str

class RepoOwner(BaseModel):
    login: str
    id: int

class Repo(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    owner: RepoOwner
    html_url: str
    default_branch: str

class Chat(BaseModel):
    id: str
    projectId: str
    userEmail: str
    message: str
    pullRequestUrl: str
    createdAt: str
    chatUrl: str
    seen: bool
