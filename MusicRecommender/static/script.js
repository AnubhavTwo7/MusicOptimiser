// Global state
let currentUser = null;
let selectedSongs = [];

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in
    const savedUser = localStorage.getItem('currentUser');
    if (savedUser) {
        currentUser = JSON.parse(savedUser);
        updateAuthUI();
    }
    
    // Load initial recommendations
    getRecommendations('pop');
    
    // Set up form handlers
    setupFormHandlers();
    
    // Load public playlists
    loadPlaylists();
});

// Navigation
function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Show selected section
    document.getElementById(sectionName).classList.add('active');
    
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Load section-specific data
    switch(sectionName) {
        case 'browse':
            loadPlaylists();
            break;
        case 'profile':
            if (currentUser) {
                loadUserProfile();
            } else {
                showToast('Please login to view profile', 'error');
                showSection('home');
            }
            break;
    }
}

// Authentication
function showLoginModal() {
    document.getElementById('loginModal').style.display = 'block';
    closeModal('registerModal');
}

function showRegisterModal() {
    document.getElementById('registerModal').style.display = 'block';
    closeModal('loginModal');
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function setupFormHandlers() {
    // Login form
    document.getElementById('loginForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;
        
        try {
            showLoading();
            
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            
            const response = await fetch('/api/users/login', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                currentUser = data.user;
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                updateAuthUI();
                closeModal('loginModal');
                showToast('Login successful!', 'success');
            } else {
                showToast(data.detail || 'Login failed', 'error');
            }
        } catch (error) {
            showToast('Login error: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    });
    
    // Register form
    document.getElementById('registerForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const username = document.getElementById('registerUsername').value;
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;
        
        try {
            showLoading();
            
            const formData = new FormData();
            formData.append('username', username);
            formData.append('email', email);
            formData.append('password', password);
            
            const response = await fetch('/api/users/register', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                closeModal('registerModal');
                showToast('Registration successful! Please login.', 'success');
                showLoginModal();
            } else {
                showToast(data.detail || 'Registration failed', 'error');
            }
        } catch (error) {
            showToast('Registration error: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    });
    
    // Create playlist form
    document.getElementById('createPlaylistForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (!currentUser) {
            showToast('Please login to create playlists', 'error');
            return;
        }
        
        const name = document.getElementById('playlistName').value;
        const description = document.getElementById('playlistDescription').value;
        const isPublic = document.getElementById('isPublic').checked;
        
        try {
            showLoading();
            
            const formData = new FormData();
            formData.append('user_id', currentUser.id);
            formData.append('name', name);
            formData.append('description', description);
            formData.append('is_public', isPublic);
            formData.append('song_ids', selectedSongs.join(','));
            
            const response = await fetch('/api/playlists/create', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showToast('Playlist created successfully!', 'success');
                
                // Reset form
                document.getElementById('createPlaylistForm').reset();
                selectedSongs = [];
                updateSelectedSongs();
                
                // Switch to browse section
                showSection('browse');
                loadPlaylists();
            } else {
                showToast(data.detail || 'Failed to create playlist', 'error');
            }
        } catch (error) {
            showToast('Error creating playlist: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    });
}

function updateAuthUI() {
    if (currentUser) {
        document.getElementById('loginBtn').style.display = 'none';
        document.getElementById('logoutBtn').style.display = 'block';
        document.getElementById('profileBtn').style.display = 'block';
    } else {
        document.getElementById('loginBtn').style.display = 'block';
        document.getElementById('logoutBtn').style.display = 'none';
        document.getElementById('profileBtn').style.display = 'none';
    }
}

function logout() {
    currentUser = null;
    localStorage.removeItem('currentUser');
    updateAuthUI();
    showToast('Logged out successfully', 'success');
    showSection('home');
}

// Recommendations
async function getRecommendations(genre, limit = 20) {
    try {
        showLoading();
        
        const response = await fetch(`/api/recommendations/search?genre=${genre}&limit=${limit}`);
        const data = await response.json();
        
        if (response.ok) {
            displayRecommendations(data.recommendations);
        } else {
            showToast('Failed to get recommendations', 'error');
        }
    } catch (error) {
        showToast('Error getting recommendations: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function getMoodRecommendations(mood, limit = 20) {
    try {
        showLoading();
        
        const response = await fetch(`/api/recommendations/mood?mood=${mood}&limit=${limit}`);
        const data = await response.json();
        
        if (response.ok) {
            displayRecommendations(data.recommendations);
        } else {
            showToast('Failed to get mood recommendations', 'error');
        }
    } catch (error) {
        showToast('Error getting mood recommendations: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function getArtistRecommendations(artistName, limit = 10) {
    try {
        showLoading();
        
        const response = await fetch(`/api/recommendations/artist?artist_name=${encodeURIComponent(artistName)}&limit=${limit}`);
        const data = await response.json();
        
        if (response.ok) {
            return data.recommendations;
        } else {
            showToast('Failed to get artist recommendations', 'error');
            return [];
        }
    } catch (error) {
        showToast('Error getting artist recommendations: ' + error.message, 'error');
        return [];
    } finally {
        hideLoading();
    }
}

function displayRecommendations(recommendations) {
    const container = document.getElementById('recommendations');
    
    if (!recommendations || recommendations.length === 0) {
        container.innerHTML = '<p class="text-center">No recommendations found.</p>';
        return;
    }
    
    container.innerHTML = recommendations.map(song => `
        <div class="music-card">
            ${song.image_url ? `<img src="${song.image_url}" alt="${song.name}" class="song-image">` : ''}
            <div class="song-title">${song.name}</div>
            <div class="song-artist">${song.artist}</div>
            <div class="song-album">${song.album}</div>
            <div class="song-stats">
                <span class="popularity">♪ ${song.popularity}</span>
                <span class="duration">${formatDuration(song.duration_ms)}</span>
            </div>
            <div class="song-actions">
                <button class="btn-primary" onclick="addToSelectedSongs('${song.id}', '${song.name}', '${song.artist}')">
                    <i class="fas fa-plus"></i> Add
                </button>
                <a href="${song.external_url}" target="_blank" class="btn-secondary" style="text-decoration: none; text-align: center; display: block;">
                    <i class="fas fa-external-link-alt"></i> Spotify
                </a>
            </div>
        </div>
    `).join('');
}

// Playlist management
async function loadPlaylists() {
    try {
        showLoading();
        
        const response = await fetch('/api/playlists');
        const data = await response.json();
        
        if (response.ok) {
            displayPlaylists(data.playlists);
        } else {
            showToast('Failed to load playlists', 'error');
        }
    } catch (error) {
        showToast('Error loading playlists: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function loadUserPlaylists() {
    if (!currentUser) {
        showToast('Please login to view your playlists', 'error');
        return;
    }
    
    try {
        showLoading();
        
        const response = await fetch(`/api/playlists?user_id=${currentUser.id}`);
        const data = await response.json();
        
        if (response.ok) {
            displayPlaylists(data.playlists);
        } else {
            showToast('Failed to load your playlists', 'error');
        }
    } catch (error) {
        showToast('Error loading your playlists: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function displayPlaylists(playlists) {
    const container = document.getElementById('playlists');
    
    if (!playlists || playlists.length === 0) {
        container.innerHTML = '<p class="text-center">No playlists found.</p>';
        return;
    }
    
    container.innerHTML = playlists.map(playlist => `
        <div class="playlist-card" onclick="showPlaylistDetails(${playlist.id})">
            <div class="playlist-name">${playlist.name}</div>
            <div class="playlist-creator">by ${playlist.creator}</div>
            <div class="playlist-description">${playlist.description || 'No description'}</div>
            <div class="playlist-stats">
                <span>${playlist.song_count} songs</span>
                <span>${new Date(playlist.created_at).toLocaleDateString()}</span>
            </div>
        </div>
    `).join('');
}

async function showPlaylistDetails(playlistId) {
    try {
        showLoading();
        
        const response = await fetch(`/api/playlists/${playlistId}`);
        const data = await response.json();
        
        if (response.ok) {
            const modal = document.getElementById('playlistModal');
            const detail = document.getElementById('playlistDetail');
            
            detail.innerHTML = `
                <h2>${data.playlist.name}</h2>
                <p><strong>Creator:</strong> ${data.playlist.creator}</p>
                <p><strong>Description:</strong> ${data.playlist.description || 'No description'}</p>
                <p><strong>Songs:</strong> ${data.playlist.song_count} | <strong>Duration:</strong> ${formatDuration(data.playlist.total_duration_ms)}</p>
                <hr style="margin: 1rem 0;">
                <h3>Songs</h3>
                <div class="music-grid">
                    ${data.songs.map(song => `
                        <div class="music-card">
                            ${song.image_url ? `<img src="${song.image_url}" alt="${song.name}" class="song-image">` : ''}
                            <div class="song-title">${song.name}</div>
                            <div class="song-artist">${song.artist}</div>
                            <div class="song-album">${song.album}</div>
                            <div class="song-stats">
                                <span class="popularity">♪ ${song.popularity}</span>
                                <span class="duration">${formatDuration(song.duration_ms)}</span>
                            </div>
                            <div class="song-actions">
                                <a href="${song.external_url}" target="_blank" class="btn-primary" style="text-decoration: none; text-align: center; display: block;">
                                    <i class="fas fa-external-link-alt"></i> Listen
                                </a>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            
            modal.style.display = 'block';
        } else {
            showToast('Failed to load playlist details', 'error');
        }
    } catch (error) {
        showToast('Error loading playlist details: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Selected songs management
function addToSelectedSongs(songId, songName, artist) {
    if (!selectedSongs.includes(songId)) {
        selectedSongs.push(songId);
        updateSelectedSongs();
        showToast(`Added "${songName}" to playlist`, 'success');
    } else {
        showToast('Song already in playlist', 'error');
    }
}

function removeFromSelectedSongs(songId) {
    selectedSongs = selectedSongs.filter(id => id !== songId);
    updateSelectedSongs();
    showToast('Song removed from playlist', 'success');
}

function updateSelectedSongs() {
    const container = document.getElementById('selectedSongs');
    const count = document.getElementById('songCount');
    
    count.textContent = selectedSongs.length;
    
    if (selectedSongs.length === 0) {
        container.innerHTML = '<p>No songs selected yet. Add songs from recommendations above.</p>';
        return;
    }
    
    // For simplicity, just show song IDs. In a real app, you'd fetch song details
    container.innerHTML = selectedSongs.map((songId, index) => `
        <div class="selected-song">
            <span>Song ${index + 1}: ${songId}</span>
            <button class="remove-song" onclick="removeFromSelectedSongs('${songId}')">Remove</button>
        </div>
    `).join('');
}

// Playlist creation helpers
async function addGenreRecommendations() {
    const genre = document.getElementById('genreSelect').value;
    if (!genre) {
        showToast('Please select a genre', 'error');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch(`/api/recommendations/search?genre=${genre}&limit=10`);
        const data = await response.json();
        
        if (response.ok && data.recommendations) {
            data.recommendations.forEach(song => {
                if (!selectedSongs.includes(song.id)) {
                    selectedSongs.push(song.id);
                }
            });
            updateSelectedSongs();
            showToast(`Added ${genre} recommendations`, 'success');
        }
    } catch (error) {
        showToast('Error adding genre recommendations', 'error');
    } finally {
        hideLoading();
    }
}

async function addMoodRecommendations() {
    const mood = document.getElementById('moodSelect').value;
    if (!mood) {
        showToast('Please select a mood', 'error');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch(`/api/recommendations/mood?mood=${mood}&limit=10`);
        const data = await response.json();
        
        if (response.ok && data.recommendations) {
            data.recommendations.forEach(song => {
                if (!selectedSongs.includes(song.id)) {
                    selectedSongs.push(song.id);
                }
            });
            updateSelectedSongs();
            showToast(`Added ${mood} mood recommendations`, 'success');
        }
    } catch (error) {
        showToast('Error adding mood recommendations', 'error');
    } finally {
        hideLoading();
    }
}

async function addArtistRecommendations() {
    const artist = document.getElementById('artistInput').value.trim();
    if (!artist) {
        showToast('Please enter an artist name', 'error');
        return;
    }
    
    const recommendations = await getArtistRecommendations(artist, 10);
    if (recommendations.length > 0) {
        recommendations.forEach(song => {
            if (!selectedSongs.includes(song.id)) {
                selectedSongs.push(song.id);
            }
        });
        updateSelectedSongs();
        showToast(`Added recommendations based on ${artist}`, 'success');
        document.getElementById('artistInput').value = '';
    }
}

// Search functionality
async function searchMusic() {
    const query = document.getElementById('searchInput').value.trim();
    const type = document.querySelector('input[name="searchType"]:checked').value;
    
    if (!query) {
        showToast('Please enter a search query', 'error');
        return;
    }
    
    try {
        showLoading();
        
        const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&type=${type}&limit=20`);
        const data = await response.json();
        
        if (response.ok) {
            displaySearchResults(data.results, type);
        } else {
            showToast('Search failed', 'error');
        }
    } catch (error) {
        showToast('Search error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function displaySearchResults(results, type) {
    const container = document.getElementById('searchResults');
    
    if (!results || results.length === 0) {
        container.innerHTML = '<p class="text-center">No results found.</p>';
        return;
    }
    
    if (type === 'track') {
        container.innerHTML = results.map(song => `
            <div class="music-card">
                ${song.image_url ? `<img src="${song.image_url}" alt="${song.name}" class="song-image">` : ''}
                <div class="song-title">${song.name}</div>
                <div class="song-artist">${song.artist}</div>
                <div class="song-album">${song.album}</div>
                <div class="song-stats">
                    <span class="popularity">♪ ${song.popularity}</span>
                    <span class="duration">${formatDuration(song.duration_ms)}</span>
                </div>
                <div class="song-actions">
                    <button class="btn-primary" onclick="addToSelectedSongs('${song.id}', '${song.name}', '${song.artist}')">
                        <i class="fas fa-plus"></i> Add
                    </button>
                    <a href="${song.external_url}" target="_blank" class="btn-secondary" style="text-decoration: none; text-align: center; display: block;">
                        <i class="fas fa-external-link-alt"></i> Spotify
                    </a>
                </div>
            </div>
        `).join('');
    } else if (type === 'artist') {
        container.innerHTML = results.map(artist => `
            <div class="music-card">
                ${artist.image_url ? `<img src="${artist.image_url}" alt="${artist.name}" class="song-image">` : ''}
                <div class="song-title">${artist.name}</div>
                <div class="song-artist">Popularity: ${artist.popularity}</div>
                <div class="song-album">Followers: ${artist.followers.toLocaleString()}</div>
                <div class="song-stats">
                    <span class="popularity">Genres: ${artist.genres.slice(0, 2).join(', ')}</span>
                </div>
                <div class="song-actions">
                    <button class="btn-primary" onclick="getArtistRecommendations('${artist.name}')">
                        <i class="fas fa-music"></i> Get Songs
                    </button>
                    <a href="${artist.external_url}" target="_blank" class="btn-secondary" style="text-decoration: none; text-align: center; display: block;">
                        <i class="fas fa-external-link-alt"></i> Spotify
                    </a>
                </div>
            </div>
        `).join('');
    }
}

// User profile
async function loadUserProfile() {
    if (!currentUser) return;
    
    try {
        showLoading();
        
        const response = await fetch(`/api/users/${currentUser.id}`);
        const data = await response.json();
        
        if (response.ok) {
            const container = document.getElementById('profileInfo');
            const user = data.user;
            
            container.innerHTML = `
                <div class="profile-card">
                    <h3>${user.username}</h3>
                    <p><strong>Email:</strong> ${user.email}</p>
                    <p><strong>Member Since:</strong> ${new Date(user.created_at).toLocaleDateString()}</p>
                    <p><strong>Playlists Created:</strong> ${user.playlist_count}</p>
                    <p><strong>Total Listens:</strong> ${user.total_listens}</p>
                </div>
            `;
        } else {
            showToast('Failed to load profile', 'error');
        }
    } catch (error) {
        showToast('Error loading profile: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Utility functions
function formatDuration(ms) {
    if (!ms) return '0:00';
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Handle search on Enter key
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchMusic();
        }
    });
});

// Close modals when clicking outside
window.addEventListener('click', function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
});
