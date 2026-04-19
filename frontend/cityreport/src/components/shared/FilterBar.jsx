import React from 'react';
import { Search, Filter } from 'lucide-react';
import Card from './Card';
import './FilterBar.css';

const FilterBar = ({ onSearch, onFilterChange, onSortChange }) => {
    return (
      <Card className="filter-bar mb-lg" padding="sm">
        <div className="flex flex-col md:flex-row gap-md items-center w-full">
          <div className="search-container flex-1 w-full">
            <Search size={18} className="search-icon" />
            <input
              type="text"
              placeholder="Search reports..."
              className="search-input"
              onChange={(e) => onSearch(e.target.value)}
            />
          </div>

          <div className="filters-container flex gap-sm w-full md:w-auto overflow-x-auto">
            <select
              className="filter-select"
              onChange={(e) => onFilterChange("status", e.target.value)}
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
            </select>

            <select
              className="filter-select"
              onChange={(e) => onSortChange(e.target.value)}
            >
              <option value="upvotes">Most Upvoted</option>
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="severity">Highest Severity</option>
            </select>
          </div>
        </div>
      </Card>
    );
};

export default FilterBar;
