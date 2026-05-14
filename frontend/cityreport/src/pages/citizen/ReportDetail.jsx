import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, MapPin, Calendar, ThumbsUp, CheckCircle, AlertTriangle, Trash2 } from 'lucide-react';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import Navbar from '../../components/shared/Navbar';
import Button from '../../components/shared/Button';
import Card from '../../components/shared/Card';
import Badge from '../../components/shared/Badge';
import AIAnalysisCard from '../../components/AIAnalysisCard';
import { useAuth } from '../../contexts/AuthContext';
import './ReportDetail.css';
import { getImageUrl } from '../../utils/image';
import api from '../../api';

// Fix default leaflet marker icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const ReportDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const [report, setReport]           = useState(null);
  const [loading, setLoading]         = useState(true);
  const [upvoted, setUpvoted]         = useState(false);
  const [geoAddress, setGeoAddress]   = useState('');
  const [disputeText, setDisputeText] = useState('');
  const [showDispute, setShowDispute] = useState(false);
  const [showReopenForm, setShowReopenForm] = useState(false);
  const [reopenText, setReopenText]   = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Re-fetch whenever the URL (including navigation state) changes so
  // clicking a notification for the same report always shows fresh data.
  useEffect(() => {
    setLoading(true);
    setReport(null);
    setGeoAddress('');
    api.get(`/reports/${id}`)
      .then(({ data }) => {
        setReport(data);
        // Restore upvote state from localStorage
        const key = `upvoted_${user?.id}_${data.id}`;
        setUpvoted(localStorage.getItem(key) === '1');
        // Reverse geocode coordinates
        if (data.latitude && data.longitude) {
          fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${data.latitude}&lon=${data.longitude}`, {
            headers: { 'Accept-Language': 'en' },
          })
            .then(r => r.json())
            .then(geo => setGeoAddress(geo.display_name || ''))
            .catch(() => {});
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id, location.key]);

  if (loading) return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="container py-xl text-center"><p className="text-muted">Loading report details...</p></div>
    </div>
  );

  if (!report) return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="container py-xl text-center">
        <p className="text-danger">Report not found.</p>
        <Button variant="ghost" onClick={() => navigate(-1)} icon={ArrowLeft}>Go Back</Button>
      </div>
    </div>
  );

  const isOwner = user && Number(user.id) === Number(report.user_id);

  const getStatusVariant = (s = '') => {
    if (s === 'resolved' || s === 'closed') return 'success';
    if (s === 'in_progress') return 'warning';
    if (s === 'reopened') return 'danger';
    if (s === 'pending') return 'danger';
    return 'neutral';
  };

  const statusLabel = (s = '') => ({
    pending: 'Pending', in_progress: 'In Progress',
    resolved: 'Resolved', closed: 'Closed', reopened: 'Reopened',
  }[s] || s);

  const handleUpvote = async () => {
    const newUpvoted = !upvoted;
    const newCount = newUpvoted ? report.upvotes + 1 : report.upvotes - 1;
    setUpvoted(newUpvoted);
    setReport(prev => ({ ...prev, upvotes: newCount }));
    const key = `upvoted_${user?.id}_${report.id}`;
    if (newUpvoted) localStorage.setItem(key, '1');
    else localStorage.removeItem(key);
    try {
      const { data } = await api.post(`/reports/${report.id}/upvote`);
      setReport(prev => ({ ...prev, upvotes: data.upvotes ?? prev.upvotes }));
    } catch {
      setUpvoted(upvoted);
      setReport(prev => ({ ...prev, upvotes: report.upvotes }));
      if (upvoted) localStorage.setItem(key, '1');
      else localStorage.removeItem(key);
    }
  };

  const handleVerify = async () => {
    if (!window.confirm('Confirm that this issue has been resolved and close the report?')) return;
    setActionLoading(true);
    try {
      const { data } = await api.post(`/reports/${id}/verify`);
      setReport(data);
    } catch {
      alert('Failed to verify. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDispute = async () => {
    if (!disputeText.trim()) { alert('Please describe why the issue is not resolved.'); return; }
    setActionLoading(true);
    try {
      const { data } = await api.post(`/reports/${id}/reopen`, null, { params: { feedback: disputeText } });
      setReport(data);
      setShowDispute(false);
      setDisputeText('');
    } catch {
      alert('Failed to submit dispute. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to permanently delete this report? This cannot be undone.')) return;
    setActionLoading(true);
    try {
      await api.delete(`/reports/${id}`);
      navigate('/citizen/reports');
    } catch {
      alert('Failed to delete report.');
      setActionLoading(false);
    }
  };

  const handleReopen = async (feedback) => {
    if (!feedback.trim()) { alert('Please explain why you want to reopen this report.'); return; }
    setActionLoading(true);
    try {
      const { data } = await api.post(`/reports/${id}/reopen`, null, { params: { feedback } });
      setReport(data);
      setShowReopenForm(false);
      setReopenText('');
    } catch {
      alert('Failed to reopen. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container py-lg">

        {/* Back + title row */}
        <div className="flex items-center gap-md mb-lg">
          <Button variant="ghost" size="sm" icon={ArrowLeft} onClick={() => navigate(-1)}>Back</Button>
          <div className="flex-1">
            <div className="flex items-center gap-sm flex-wrap">
              <h1 className="text-2xl font-bold">{report.title}</h1>
              <Badge variant={getStatusVariant(report.status)}>{statusLabel(report.status)}</Badge>
            </div>
          </div>
        </div>

        {/* Owner action banner */}
        {isOwner && report.status === 'resolved' && (
          <div className="owner-action-banner mb-lg">
            <div className="banner-content">
              <CheckCircle size={20} className="banner-icon" />
              <div>
                <p className="banner-title">This report has been marked as resolved</p>
                <p className="banner-sub">Please confirm if the issue has actually been fixed.</p>
              </div>
            </div>
            <div className="banner-actions">
              {!showDispute ? (
                <>
                  <Button variant="primary" size="sm" onClick={handleVerify} disabled={actionLoading}>
                    ✓ Verify &amp; Close
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setShowDispute(true)} disabled={actionLoading}>
                    Not Resolved? Dispute
                  </Button>
                </>
              ) : (
                <div className="dispute-form">
                  <textarea
                    className="form-control dispute-textarea"
                    placeholder="Describe why the issue is still not resolved..."
                    value={disputeText}
                    onChange={(e) => setDisputeText(e.target.value)}
                    rows={3}
                  />
                  <div className="flex gap-sm justify-end mt-sm">
                    <Button variant="ghost" size="sm" onClick={() => { setShowDispute(false); setDisputeText(''); }}>
                      Cancel
                    </Button>
                    <Button variant="danger" size="sm" icon={AlertTriangle} onClick={handleDispute} disabled={actionLoading}>
                      Submit Dispute
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {isOwner && report.status === 'reopened' && (
          <div className="owner-action-banner banner-warning mb-lg">
            <AlertTriangle size={20} className="banner-icon" />
            <p className="banner-title">Your dispute has been submitted. Officers will review it.</p>
          </div>
        )}

        {isOwner && report.status === 'closed' && (
          <div className="owner-action-banner banner-success mb-lg">
            <div className="banner-content">
              <CheckCircle size={20} className="banner-icon" />
              <div>
                <p className="banner-title">Report closed. Thank you for helping improve the city!</p>
                <p className="banner-sub">If this was closed by mistake, you can reopen it.</p>
              </div>
            </div>
            <div className="banner-actions">
              {!showReopenForm ? (
                <Button variant="outline" size="sm" onClick={() => setShowReopenForm(true)} disabled={actionLoading}>
                  Reopen Report
                </Button>
              ) : (
                <div className="dispute-form">
                  <textarea
                    className="form-control dispute-textarea"
                    placeholder="Why are you reopening this report?"
                    value={reopenText}
                    onChange={(e) => setReopenText(e.target.value)}
                    rows={3}
                  />
                  <div className="flex gap-sm justify-end mt-sm">
                    <Button variant="ghost" size="sm" onClick={() => { setShowReopenForm(false); setReopenText(''); }}>
                      Cancel
                    </Button>
                    <Button variant="danger" size="sm" icon={AlertTriangle} onClick={() => handleReopen(reopenText)} disabled={actionLoading}>
                      Confirm Reopen
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="report-detail-container">
          <div className="report-detail-main">
            <Card className="mb-lg p-none overflow-hidden">
              <div className="report-image-container">
                <img
                  src={getImageUrl(report.image_url || report.imageUrl)}
                  alt={report.title}
                  className="report-detail-image"
                  onError={(e) => { e.target.onerror = null; e.target.src = 'https://via.placeholder.com/800x400?text=No+Image'; }}
                />
              </div>
              <div className="p-lg">
                <h3 className="mb-sm">Description</h3>
                <p className="report-description text-secondary">{report.description || 'No description provided.'}</p>
              </div>
            </Card>

            <AIAnalysisCard report={report} />
          </div>

          <div className="report-detail-sidebar">
            <Card className="mb-md">
              <h3 className="mb-md">Report Details</h3>
              <div className="info-list">
                <div className="info-item">
                  <span className="info-label">Status</span>
                  <Badge variant={getStatusVariant(report.status)}>{statusLabel(report.status)}</Badge>
                </div>
                <div className="info-item">
                  <span className="info-label">Category</span>
                  <span className="info-value">{report.category?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'General'}</span>
                </div>
                <div className="info-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <span className="info-label">Location</span>
                  {report.latitude && report.longitude && (
                    <div style={{ borderRadius: '6px', overflow: 'hidden', border: '1px solid var(--border)', height: '120px' }}>
                      <MapContainer
                        center={[report.latitude, report.longitude]}
                        zoom={15}
                        style={{ height: '100%', width: '100%' }}
                        zoomControl={false}
                        dragging={false}
                        scrollWheelZoom={false}
                        doubleClickZoom={false}
                        attributionControl={false}
                      >
                        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                        <Marker position={[report.latitude, report.longitude]} />
                      </MapContainer>
                    </div>
                  )}
                  <div className="flex items-start gap-xs">
                    <MapPin size={14} className="text-muted" style={{ marginTop: 2, flexShrink: 0 }} />
                    <span className="info-value text-sm">
                      {geoAddress || report.location || `${report.latitude?.toFixed(5)}, ${report.longitude?.toFixed(5)}`}
                    </span>
                  </div>
                </div>
                <div className="info-item">
                  <span className="info-label">Reported On</span>
                  <div className="flex items-center gap-xs">
                    <Calendar size={16} className="text-muted" />
                    <span className="info-value text-sm">{new Date(report.created_at || report.createdAt).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="info-item">
                  <span className="info-label">Priority</span>
                  <Badge variant={
                    ['high','critical'].includes(report.priority) ? 'danger' :
                    report.priority === 'low' ? 'success' : 'neutral'
                  }>
                    {report.priority?.toUpperCase() || 'MEDIUM'}
                  </Badge>
                </div>
                <div className="info-item">
                  <span className="info-label">Upvotes</span>
                  <button className="upvote-btn" onClick={handleUpvote}>
                    <ThumbsUp size={15} className={upvoted ? 'upvoted' : ''} />
                    <span>{report.upvotes ?? 0}</span>
                  </button>
                </div>
              </div>
            </Card>

            {/* Owner: delete */}
            {isOwner && !['closed'].includes(report.status) && (
              <Card>
                <h3 className="mb-md text-sm font-semibold">Manage Report</h3>
                <Button
                  variant="outline"
                  size="sm"
                  icon={Trash2}
                  onClick={handleDelete}
                  disabled={actionLoading}
                  style={{ width: '100%', color: 'var(--danger)', borderColor: 'var(--danger)' }}
                >
                  Delete Report
                </Button>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportDetail;
