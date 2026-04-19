import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Camera, X, ArrowLeft } from 'lucide-react';
import Navbar from '../../components/shared/Navbar';
import Button from '../../components/shared/Button';
import Card from '../../components/shared/Card';
import api from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import './NewReport.css';
import LocationPicker from '../../components/shared/LocationPicker';

const NewReport = () => {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [formData, setFormData] = useState({
    title: "",
    location: "",
    description: "",
    latitude: "",
    longitude: "",
  });
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState('');
  const [error, setError] = useState(null);

  // Auto-locate on mount; silent fallback if denied
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setFormData(prev => ({
          ...prev,
          latitude: coords.latitude.toFixed(6),
          longitude: coords.longitude.toFixed(6),
          location: `${coords.latitude.toFixed(6)}, ${coords.longitude.toFixed(6)}`,
        }));
      },
      () => {},
      { timeout: 8000 }
    );
  }, []);

  const handleChange = (e) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleImageUpload = (e) => {
    const files = Array.from(e.target.files);
    const newImages = files.map((file) => ({
      file,
      preview: URL.createObjectURL(file),
    }));
    setImages((prev) => [...prev, ...newImages].slice(0, 5)); // Max 5 images
  };

  const removeImage = (index) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setLoadingStage('Uploading…');
    setError(null);

    try {
      if (!formData.latitude || !formData.longitude) {
        throw new Error("Please provide a location");
      }

      let imageUrl = null;
      if (images.length > 0) {
        try {
          const fd = new FormData();
          fd.append('file', images[0].file);
          const uploadResponse = await api.post('/upload/image', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          imageUrl = uploadResponse.data.image_url;
        } catch {
          throw new Error('Failed to upload image. Please try again.');
        }
      }

      setLoadingStage('Running AI analysis…');

      const reportData = {
        title: formData.title,
        description: formData.description,
        category: "road_issues",
        latitude: parseFloat(formData.latitude),
        longitude: parseFloat(formData.longitude),
        image_url: imageUrl,
      };

      const response = await api.post("/reports/", reportData);

      if (response.data.id) {
        navigate(`/citizen/report/${response.data.id}`);
      } else {
        navigate("/citizen/dashboard");
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        "Failed to submit report. Please try again.",
      );
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setFormData((prev) => ({
            ...prev,
            latitude: position.coords.latitude.toFixed(6),
            longitude: position.coords.longitude.toFixed(6),
            location: `${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}`,
          }));
        },
        (error) => {
          console.error("Error getting location:", error);
          alert("Could not fetch location. Please check browser permissions.");
        },
        { enableHighAccuracy: true }
      );
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="container py-lg">
        <div className="report-form-header">
          <Button
            variant="ghost"
            icon={ArrowLeft}
            onClick={() => navigate("/citizen/dashboard")}
          >
            Back
          </Button>
          <h1 className="text-2xl">Report a Road Issue</h1>
        </div>

        {error && (
          <div
            style={{
              padding: "12px 16px",
              marginBottom: "20px",
              backgroundColor: "#fee",
              border: "1px solid #fcc",
              borderRadius: "8px",
              color: "#c33",
            }}
          >
            <strong>Error:</strong> {error}
          </div>
        )}

        <div className="report-form-container">
          <Card>
            <form onSubmit={handleSubmit} className="report-form">
              <div className="form-group">
                <label htmlFor="title" className="form-label">
                  Issue Title *
                </label>
                <input
                  id="title"
                  name="title"
                  type="text"
                  className="form-input"
                  placeholder="Brief description of the issue"
                  value={formData.title}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="location" className="form-label mb-2 block">
                  Location *
                </label>

                {/* Visual Map Picker */}
                <LocationPicker
                  position={
                    formData.latitude && formData.longitude
                      ? { lat: parseFloat(formData.latitude), lng: parseFloat(formData.longitude) }
                      : null
                  }
                  onLocationChange={(lat, lng) => {
                    setFormData(prev => ({
                      ...prev,
                      latitude: lat,
                      longitude: lng,
                      location: `${lat.toFixed(6)}, ${lng.toFixed(6)}`
                    }));
                  }}
                />

                <div className="location-input-group flex gap-2">
                  <div className="input-with-icon flex-1 relative">
                    <input
                      id="location"
                      name="location"
                      type="text"
                      className="form-input pl-8 w-full"
                      placeholder="Coordinates will appear here"
                      value={formData.location}
                      readOnly
                    />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={getCurrentLocation}
                    icon={MapPin}
                  >
                    Use GPS
                  </Button>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="description" className="form-label">
                  Description *
                </label>
                <textarea
                  id="description"
                  name="description"
                  className="form-textarea"
                  placeholder="Describe the pothole, road break, cracking, or surface damage"
                  rows="5"
                  value={formData.description}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Photos (Optional, max 5)</label>
                <div className="image-upload-container">
                  <input
                    type="file"
                    id="image-upload"
                    accept="image/*"
                    multiple
                    onChange={handleImageUpload}
                    style={{ display: 'none' }}
                  />
                  <label htmlFor="image-upload" className="image-upload-btn">
                    <Camera size={24} />
                    <span>{images.length > 0 ? `${images.length} photo${images.length > 1 ? 's' : ''} selected` : 'Choose Photos'}</span>
                  </label>
                </div>

                {images.length > 0 && (
                  <div className="image-preview-grid">
                    {images.map((img, index) => (
                      <div key={index} className="image-preview-item">
                        <img src={img.preview} alt={`Preview ${index + 1}`} />
                        <button
                          type="button"
                          className="image-remove-btn"
                          onClick={() => removeImage(index)}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {loading && (
                <div className="submit-loading-banner">
                  <span className="submit-spinner" />
                  <span>{loadingStage}</span>
                </div>
              )}

              <div className="form-actions">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate("/citizen/dashboard")}
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={loading}>
                  {loading ? 'Please wait…' : 'Submit Report'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      </main>
    </div>
  );
};

export default NewReport;
