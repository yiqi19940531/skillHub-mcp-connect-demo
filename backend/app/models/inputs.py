from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class Grant(Input):
    type: Literal["user", "team"]
    id: str = Field(min_length=1, max_length=120)


class Upload(Input):
    team_id: str
    visibility: Literal["private", "team", "enterprise", "custom"] = "team"
    skill_md: str | None = Field(default=None, max_length=65536)
    upload_id: str | None = None
    version: str = "0.1.0"
    skill_id: str | None = None
    display_name: str | None = Field(default=None, max_length=100)
    category_id: str | None = None
    tags: list[str] | None = None
    acl: list[Grant] | None = None
    request_id: str | None = Field(default=None, max_length=128)


class PrepareUpload(Input):
    team_id: str
    filename: str
    size: int
    sha256: str


class SkillRef(Input):
    skill_id: str


class VersionRef(Input):
    version: str


class Decision(Input):
    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=2000)


class Sharing(Input):
    visibility: Literal["private", "team", "enterprise", "custom"]
    acl: list[Grant] = []


class CollectionCreate(Input):
    team_id: str
    name: str
    acl: list[Grant] = []


class CollectionEdit(Input):
    revision: int
    name: str | None = None
    archived: bool = False


class SkillEdit(Input):
    revision: int
    display_name: str | None = None
    category_id: str | None = None
    tags: list[str] | None = None


class VersionStatus(Input):
    status: Literal["deprecated", "revoked"]


class Install(Input):
    skill_id: str
    client: str
    scope: Literal["project", "user"] = "project"
    version: str | None = None
    workspace_id: str = "unspecified"


class InstallReport(Input):
    skill_id: str
    version: str
    client: str
    scope: Literal["project", "user"]
    status: Literal["written", "discovered", "failed", "cancelled", "uninstalled"]
    installation_id: str
    operation: Literal["install", "update", "uninstall"] = "install"
    target_path: str | None = None
    digest: str | None = None
    files_written: bool = False
    client_discovered: bool = False
    workspace_id: str = "unspecified"
    request_id: str | None = None


class UpdateInstall(Input):
    installation_id: str
    version: str | None = None


class Uninstall(Input):
    installation_id: str


class Rating(Input):
    version: str
    score: int = Field(ge=1, le=5)


class IssueCreate(Input):
    description: str = Field(min_length=1, max_length=4000)
    kind: Literal["description", "broken", "security", "other"] = "description"
    version: str | None = None


class IssueEdit(Input):
    revision: int
    status: Literal["open", "in_progress", "resolved", "closed"]
    resolution: str = Field(default="", max_length=2000)


class UserCreate(Input):
    username: str
    display_name: str
    password: str = Field(min_length=10, max_length=128)
    roles: list[str] = ["Member", "SkillAuthor"]


class UserEdit(Input):
    revision: int
    display_name: str | None = None
    disabled: bool | None = None
    roles: list[str] | None = None


class PasswordReset(Input):
    password: str = Field(min_length=10, max_length=128)


class TeamCreate(Input):
    name: str
    owner_user_id: str
    description: str = ""


class TeamEdit(Input):
    revision: int
    name: str | None = None
    description: str | None = None
    archived: bool | None = None


class MemberEdit(Input):
    user_id: str
    role: Literal["member", "owner"] = "member"
    status: Literal["active", "removed"] = "active"
