import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, SortDesc, Brain } from 'lucide-react';
import Navbar from '../../components/shared/Navbar';
import Card from '../../components/shared/Card';
import Badge from '../../components/shared/Badge';
import Button from '../../components/shared/Button';
import './AdminReports.css';
import { getImageUrl } from '../../utils/image';
import api from '../../api';

const AdminReports = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('ai_severity_score');
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => {
    fetchReports();
  }, [sortBy, filterStatus]);

  const fetchReports = async () => {
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        sort_order: 'desc',
        category: 'road_issues'
      });

      if (filterStatus !== 'all') {
        params.append('status', filterStatus);
      }

      const response = await api.get(`/reports?${params}`);
      setReports(Array.isArray(response.data) ? response.data : response.data.items || []);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching reports:', error);
      setLoading(false);
    }
  };

  const getSeverityColor = (score) => {
    if (!score) return 'neutral';
    if (score > 75) return 'danger';
    if (score > 50) return 'warning';
    if (score > 25) return 'neutral';
    return 'success';
  };

  const getSeverityLabel = (level) => {
    if (!level) return 'N/A';
    return level.toUpperCase();
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="container py-lg">
        <div className="admin-reports-header">
          <div>
            <h1 className="text-2xl mb-xs">Road Analysis Reports</h1>
            <p className="text-muted">
              View and manage road reports with local severity analysis
            </p>
          </div>
        </div>

        {/* Filters and Sorting */}
        <Card className="mb-lg">
          <div className="filters-container">
            <div className="filter-group">
              <label className="filter-label">
                <SortDesc size={16} />
                Sort By
              </label>
              <select
                className="filter-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
              >
                <option value="ai_severity_score">
                  AI Severity (High to Low)
                </option>
                <option value="created_at">Date (Newest First)</option>
                <option value="upvotes">Most Upvoted</option>
                <option value="priority">Priority</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label">
                <Filter size={16} />
                Status
              </label>
              <select
                className="filter-select"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="assigned">Assigned</option>
                <option value="in_progress">In Progress</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Reports List */}
        {loading ? (
          <div className="text-center py-lg">Loading reports...</div>
        ) : (
          <div className="reports-grid">
            {reports.map((report) => (
              <Card
                key={report.id}
                className="report-card"
                onClick={() => navigate(`/admin/reports/${report.id}`)}
              >
                <div className="report-card-header">
                  <div>
                    <h3 className="report-title">{report.title}</h3>
                    <div className="report-badges">
                      <Badge variant="neutral">ROAD ISSUE</Badge>
                      <Badge
                        variant={getSeverityColor(report.ai_severity_score)}
                      >
                        {getSeverityLabel(report.ai_severity_level)}
                      </Badge>
                    </div>
                  </div>
                  {report.ai_severity_score && (
                    <div className="severity-badge-large">
                      <Brain size={20} />
                      <span className="severity-score">
                        {Math.round(report.ai_severity_score)}
                      </span>
                      <span className="severity-max">/100</span>
                    </div>
                  )}
                </div>

                {report.image_url && (
                  <img
                    src={getImageUrl(report.image_url)}
                    alt={report.title}
                    className="report-image"
                  />
                )}

                <p className="report-description">{report.description}</p>

                {/* AI Analysis Breakdown */}
                {report.ai_severity_score && (
                  <div className="ai-breakdown">
                    <h4 className="ai-breakdown-title">AI Analysis</h4>
                    <div className="ai-scores-grid">
                      <div className="ai-score-item">
                        <span className="ai-score-label">Depth</span>
                        <span className="ai-score-value">
                          {report.pothole_depth_score !== null && report.pothole_depth_score !== undefined
                            ? `${Math.round(report.pothole_depth_score * 100)}%`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="ai-score-item">
                        <span className="ai-score-label">Spread</span>
                        <span className="ai-score-value">
                          {report.pothole_spread_score !== null && report.pothole_spread_score !== undefined
                            ? `${Math.round(report.pothole_spread_score * 100)}%`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="ai-score-item">
                        <span className="ai-score-label">Urgency</span>
                        <span className="ai-score-value">
                          {report.emotion_score
                            ? `${Math.round(report.emotion_score * 100)}%`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="ai-score-item">
                        <span className="ai-score-label">Location Risk</span>
                        <span className="ai-score-value">
                          {report.location_score
                            ? `${Math.round(report.location_score * 100)}%`
                            : "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="report-meta">
                  <span className="report-date">
                    {new Date(report.created_at).toLocaleDateString()}
                  </span>
                  <span className="report-upvotes">👍 {report.upvotes}</span>
                </div>
              </Card>
            ))}
          </div>
        )}

        {!loading && reports.length === 0 && (
          <Card className="text-center py-lg">
            <p className="text-muted">
              No reports found matching your filters.
            </p>
          </Card>
        )}
      </main>
    </div>
  );
};

export default AdminReports;
