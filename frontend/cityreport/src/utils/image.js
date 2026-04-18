import { getApiBaseUrl } from '../api';

export const getImageUrl = (url) => {
    if (!url) return 'https://via.placeholder.com/800x400?text=No+Image+Available';

    // If it's already a full URL (like unsplash), return it
    if (url.startsWith('http')) return url;

    const baseUrl = getApiBaseUrl();
    let relativePath = url.startsWith('/') ? url : `/${url}`; // Ensure leading slash

    // Auto-correct /uploads/ to /upload/image/ if it looks like a UUID path
    if (relativePath.startsWith('/uploads/')) {
        relativePath = relativePath.replace('/uploads/', '/upload/image/');
    }

    // If it's a relative path from our backend (starts with /upload)
    if (relativePath.startsWith('/upload')) {
        return `${baseUrl}${relativePath}`;
    }

    return url;
};
