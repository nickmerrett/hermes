"""GitHub collector for repository activity and releases"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from github import Github, GithubException
from github.Repository import Repository

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


class GitHubCollector(RateLimitedCollector):
    """
    Collector for GitHub activity

    Monitors:
    - Repository releases
    - Major commits to main branches
    - New repositories from organization
    - Issues and discussions (optional)
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=60)

        # Initialize GitHub API
        github_token = settings.github_token
        self.github = Github(github_token) if github_token else Github()

        # Get organization name or repository list from config
        self.org_name = customer_config.get('config', {}).get('github_org')
        self.repos = customer_config.get('config', {}).get('github_repos', [])
        self.lookback_days = 30

    def get_source_type(self) -> str:
        return "github"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect GitHub activity

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            # Collect from organization if specified
            if self.org_name:
                org_items = self._collect_from_org(self.org_name)
                items.extend(org_items)

            # Collect from specific repositories
            for repo_name in self.repos:
                if not self._check_rate_limit():
                    break
                repo_items = self._collect_from_repo(repo_name)
                items.extend(repo_items)

            self.logger.info(f"Collected {len(items)} items from GitHub")

        except Exception as e:
            self.logger.error(f"Error collecting from GitHub: {e}")
            raise

        return items

    def _collect_from_org(self, org_name: str) -> List[IntelligenceItemCreate]:
        """Collect activity from a GitHub organization"""
        items = []

        try:
            org = self.github.get_organization(org_name)

            # Get recent repositories
            repos = org.get_repos(sort='updated', direction='desc')

            for repo in repos[:10]:  # Limit to 10 most recent repos
                repo_items = self._collect_from_repo(repo.full_name, repo)
                items.extend(repo_items)

        except GithubException as e:
            self.logger.error(f"Error accessing GitHub org {org_name}: {e}")

        return items

    def _collect_from_repo(
        self,
        repo_name: str,
        repo: Repository = None
    ) -> List[IntelligenceItemCreate]:
        """Collect activity from a specific repository"""
        items = []

        try:
            if repo is None:
                repo = self.github.get_repo(repo_name)

            # Collect releases
            release_items = self._collect_releases(repo)
            items.extend(release_items)

            # Collect recent significant commits (to main/master)
            # commit_items = self._collect_commits(repo)
            # items.extend(commit_items)

        except GithubException as e:
            self.logger.error(f"Error accessing GitHub repo {repo_name}: {e}")

        return items

    def _collect_releases(self, repo: Repository) -> List[IntelligenceItemCreate]:
        """Collect releases from a repository"""
        items = []

        try:
            releases = repo.get_releases()

            cutoff_date = datetime.now() - timedelta(days=self.lookback_days)

            for release in releases[:10]:  # Limit to last 10 releases
                # Check if within lookback period
                if release.created_at < cutoff_date.replace(tzinfo=None):
                    continue

                # Create item for release
                title = f"[GitHub Release] {repo.name} {release.tag_name}"
                if release.name:
                    title = f"[GitHub Release] {repo.name} - {release.name}"

                content = release.body or "New release published"

                item = self._create_item(
                    title=title,
                    content=content,
                    url=release.html_url,
                    published_date=release.created_at,
                    raw_data={
                        'repo': repo.full_name,
                        'tag_name': release.tag_name,
                        'target_commitish': release.target_commitish,
                        'prerelease': release.prerelease,
                        'draft': release.draft,
                        'author': release.author.login if release.author else None,
                        'download_count': sum(
                            asset.download_count for asset in release.get_assets()
                        )
                    }
                )
                items.append(item)

        except GithubException as e:
            self.logger.error(f"Error collecting releases: {e}")

        return items

    def _collect_commits(self, repo: Repository) -> List[IntelligenceItemCreate]:
        """Collect significant commits (large changes to main branch)"""
        items = []

        try:
            # Get commits to default branch
            branch = repo.default_branch
            commits = repo.get_commits(sha=branch)

            cutoff_date = datetime.now() - timedelta(days=self.lookback_days)

            for commit in commits[:20]:  # Check last 20 commits
                if commit.commit.author.date < cutoff_date.replace(tzinfo=None):
                    break

                # Only include commits with significant changes (>100 total changes)
                stats = commit.stats
                if stats.total < 100:
                    continue

                title = f"[GitHub Commit] {repo.name} - {commit.commit.message.split(chr(10))[0]}"
                content = (
                    f"{commit.commit.message}\n\n"
                    f"Changes: +{stats.additions} -{stats.deletions} "
                    f"({stats.total} total)"
                )

                item = self._create_item(
                    title=title,
                    content=content,
                    url=commit.html_url,
                    published_date=commit.commit.author.date,
                    raw_data={
                        'repo': repo.full_name,
                        'sha': commit.sha,
                        'author': commit.commit.author.name,
                        'additions': stats.additions,
                        'deletions': stats.deletions,
                        'total_changes': stats.total,
                    }
                )
                items.append(item)

        except GithubException as e:
            self.logger.error(f"Error collecting commits: {e}")

        return items
