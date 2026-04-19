import { MapPin, ThumbsUp, Trash2 } from 'lucide-react';
import Card from '../shared/Card';
import Badge from '../shared/Badge';
import Button from '../shared/Button';
import './ReportCard.css';
import { getImageUrl } from '../../utils/image';
import { useAuth } from '../../contexts/AuthContext';

const ReportCard = ({ report, onUpvote, onClick, onWithdraw, isOwner }) => {
    const { user } = useAuth();
    const {
        id,
        title,
        category,
        location,
        status,
        image_url,
        imageUrl,
        upvotes,
        createdAt,
        created_at
    } = report;

    const upvoted = localStorage.getItem(`upvoted_${user?.id}_${id}`) === '1';

    const displayCategory = category === 'road_issues' ? 'Road Issue' : category;


    const STATUS_LABELS = {
        pending: 'Pending',
        in_progress: 'In Progress',
        resolved: 'Resolved',
        closed: 'Closed',
        reopened: 'Reopened',
    };

    const getStatusVariant = (status) => {
        switch (status.toLowerCase()) {
            case 'resolved':
            case 'closed': return 'success';
            case 'in_progress': return 'warning';
            case 'reopened': return 'danger';
            case 'pending': return 'danger';
            default: return 'neutral';
        }
    };

    return (
        <Card className="report-card" padding="none" onClick={() => onClick(id)}>
            <div className="report-image-container">
                <img
                    src={getImageUrl(image_url || imageUrl)}
                    alt={title}
                    className="report-image"
                    onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = 'https://via.placeholder.com/400x200?text=Load+Error';
                    }}
                />
            </div>

            <div className="report-content p-md">
                <div className="flex justify-between items-start mb-sm">
                    <h3 className="text-lg font-semibold report-title">{title}</h3>
                    <Badge variant={getStatusVariant(status)}>{STATUS_LABELS[status] || status}</Badge>
                </div>

                {location && (
                    <div className="flex items-center text-muted text-sm mb-md">
                        <MapPin size={14} className="mr-1" />
                        <span className="truncate">{location}</span>
                    </div>
                )}

                <div className="flex justify-between items-center mt-auto pt-sm border-t">
                    <div className="flex gap-md">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="action-btn"
                            onClick={(e) => {
                                e.stopPropagation();
                                onUpvote(id);
                            }}
                        >
                            <ThumbsUp size={20} style={{ color: upvoted ? 'var(--primary)' : undefined, fill: upvoted ? 'var(--primary)' : 'none' }} />
                            <span style={{ color: upvoted ? 'var(--primary)' : undefined }}>{upvotes}</span>
                        </Button>

                        {isOwner && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="action-btn action-btn-delete"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onWithdraw(id);
                                }}
                                title="Withdraw Report"
                            >
                                <Trash2 size={20} />
                            </Button>
                        )}
                    </div>

                    <span className="text-xs text-muted">
                        {(createdAt || created_at) ? new Date(createdAt || created_at).toLocaleDateString() : 'N/A'}
                    </span>
                </div>
            </div>
        </Card>
    );
};

export default ReportCard;
