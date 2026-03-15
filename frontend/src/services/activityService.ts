/**
 * Service for managing activity feed operations.
 */

import { Activity } from "@/types";
import { mockActivities } from "@/data/mock-documents";

class ActivityService {
  /**
   */
  async getRecentActivities(limit: number = 10): Promise<Activity[]> {
    await this.simulateDelay(200);
    
    return mockActivities.slice(0, limit);
    
    // Future:
    // const response = await fetch(`/api/activities?limit=${limit}`);
    // return await response.json();
  }

  /**
   * Get activities for a specific document
   */
  async getDocumentActivities(documentId: string): Promise<Activity[]> {
    await this.simulateDelay(200);
    
    return mockActivities.filter(activity => activity.documentId === documentId);
    
    // Future:
    // const response = await fetch(`/api/documents/${documentId}/activities`);
    // return await response.json();
  }

  /**
   * Get activities by user
   */
  async getUserActivities(userName: string): Promise<Activity[]> {
    await this.simulateDelay(200);
    
    return mockActivities.filter(activity => activity.user === userName);
    
    // Future:
    // const response = await fetch(`/api/users/${userName}/activities`);
    // return await response.json();
  }

  /**
   * Add new activity
   */
  async addActivity(activity: Omit<Activity, "id" | "time">): Promise<Activity> {
    await this.simulateDelay(300);
    
    const newActivity: Activity = {
      ...activity,
      id: Date.now().toString(),
      time: "nå",
    };
    
    mockActivities.unshift(newActivity);
    return newActivity;
    
    // Future:
    // const response = await fetch('/api/activities', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(activity)
    // });
    // return await response.json();
  }

  /**
   * Simulate network delay (for development only)
   */
  private simulateDelay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const activityService = new ActivityService();
