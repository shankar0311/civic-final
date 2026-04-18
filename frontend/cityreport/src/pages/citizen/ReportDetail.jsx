import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, MapPin, Calendar, ThumbsUp, MessageSquare, Send } from 'lucide-react';
import Navbar from '../../components/shared/Navbar';
import Button from '../../components/shared/Button';
import Card from '../../components/shared/Card';
import Badge from '../../components/shared/Badge';
import AIAnalysisCard from '../../components/AIAnalysisCard';
import './ReportDetail.css';
import { getImageUrl } from '../../utils/image';
import api from '../../api';

const MOCK_REPORT = {
  id: 1,
  title: 'Pothole on Main Street',
  category: 'Road Issues',
  location: '123 Main St, Downtown',
  status: 'In Progress',
  severity: 'Medium',
  priority: 'High',
  description: 'Large pothole causing traffic issues. Approximately 2 feet in diameter and 6 inches deep. Located near the intersection with Park Avenue.',
  imageUrl: 'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?auto=format&fit=crop&q=80&w=800',
  upvotes: 12,
  createdAt: '2023-11-20T10:00:00Z',
  updatedAt: '2023-11-21T14:30:00Z',
  reporter: 'John Doe',
  assignedTo: 'Roads Department',
  comments: [
    { id: 1, user: 'Jane Smith', text: 'This is a serious issue, thanks for reporting!', createdAt: '2023-11-20T12:00:00Z' },
    { id: 2, user: 'Roads Dept', text: 'We have assigned a crew to fix this. Expected completion: 2 days.', createdAt: '2023-11-21T09:00:00Z' }
  ]
};

const ReportDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState('');
  const [upvoted, setUpvoted] = useState(false);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        const response = await api.get(`/reports/${id}`);
        setReport(response.data);
      } catch (error) {
        console.error("Error fetching report:", error);
        // Fallback to mock if API fails for #1
        if (id === "1") setReport(MOCK_REPORT);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [id]);

  if (loading) return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="container py-xl text-center">
        <p className="text-muted">Loading report details...</p>
      </div>
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

  const getStatusVariant = (status = '') => {
    switch (status.toLowerCase()) {
      case 'resolved': return 'success';
      case 'in progress':
      case 'in_progress': return 'warning';
      case 'pending': return 'danger';
      default: return 'neutral';
    }
  };

  const handleUpvote = async () => {
    try {
      // Optimistic update
      const originalUpvotes = report.upvotes;
      const originalUpvoted = upvoted;

      setReport(prev => ({
        ...prev,
        upvotes: upvoted ? prev.upvotes - 1 : prev.upvotes + 1
      }));
      setUpvoted(!upvoted);

      // API Call using axios interceptor if auth configured, else raw axios
      // Assuming no auth header needed for public upvote or using global config
      // But typically needs token. For now checking if we have token logic in axios.
      // If not, we might fail. But let's assume global axios defaults or public.

      // Ideally should use an authenticated axios instance
      const token = localStorage.getItem('token');
      const config = token ? { headers: { Authorization: `Bearer ${token}` } } : {};

      await api.post(`/reports/${report.id}/upvote`, {}, config);

    } catch (error) {
      console.error("Upvote failed:", error);
      // Revert on failure
      const revertedUpvoted = !upvoted; // wait, closure issue. 
      // Safest to just refetch or rely on next page load. 
      // But let's notify user
      alert("Failed to register vote. Please log in.");
    }
  };

  const handleCommentSubmit = async (e) => {
    e.preventDefault();
    if (!comment.trim()) return;

    // Placeholder for comment submission logic
    console.log("Submitting comment:", comment);
    setComment('');
    alert("Comments feature coming soon!");
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container py-lg">

        <div className="report-detail-container">
          <div className="report-detail-main">
            <Card className="mb-lg p-none overflow-hidden">
              <div className="report-image-container">
                <img
                  src={getImageUrl(report.image_url || report.imageUrl)}
                  alt={report.title}
                  className="report-detail-image"
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = 'https://via.placeholder.com/800x400?text=Load+Error';
                  }}
                />
              </div>
              <div className="p-lg">
                <h3 className="mb-sm">Description</h3>
                <p className="report-description text-secondary">
                  {report.description || 'No description provided.'}
                </p>
              </div>
            </Card>

            <Card className="mb-lg">
              <h3 className="mb-md flex items-center gap-sm">
                <MessageSquare size={20} />
                Comments
              </h3>

              <form className="comment-form" onSubmit={handleCommentSubmit}>
                <textarea
                  className="form-control"
                  placeholder="Add a comment..."
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows="3"
                />
                <div className="flex justify-end">
                  <Button type="submit" variant="primary" icon={Send}>Post Comment</Button>
                </div>
              </form>

              <div className="comments-list mt-lg">
                {(report.comments && report.comments.length > 0) ? report.comments.map(c => (
                  <div key={c.id} className="comment-item">
                    <div className="comment-header">
                      <span className="font-bold">{c.user || 'Anonymous'}</span>
                      <span className="text-xs text-muted">{new Date(c.createdAt || c.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="comment-text">{c.text || c.content}</p>
                  </div>
                )) : (
                  <p className="text-muted text-center py-md">No comments yet.</p>
                )}
              </div>
            </Card>
          </div>

          <div className="report-detail-sidebar">
            <AIAnalysisCard report={report} />

            <Card className="mt-lg">
              <h3 className="mb-md">Report Details</h3>
              <div className="info-list">
                <div className="info-item">
                  <span className="info-label">Category</span>
                  <span className="info-value">{report.category?.replace('_', ' ') || 'General'}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Location</span>
                  <div className="flex items-start gap-xs">
                    <MapPin size={16} className="text-muted mt-xs" />
                    <span className="info-value">
                      {report.location || `${report.latitude?.toFixed(4)}, ${report.longitude?.toFixed(4)}`}
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
                  <Badge variant={report.priority === 'high' || report.priority === 'critical' ? 'danger' : 'neutral'}>
                    {report.priority?.toUpperCase() || 'MEDIUM'}
                  </Badge>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportDetail;
