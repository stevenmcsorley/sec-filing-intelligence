// services/api/subscription.service.ts
// Placeholder for subscription-related API calls

export interface SubscriptionPlan {
  id: string
  name: string
  price: number
  period: string
  features: string[]
  limits: {
    tickers: number
    alerts: number
    history: number
  }
}

export interface UserSubscription {
  plan: SubscriptionPlan
  status: 'active' | 'trial' | 'expired' | 'cancelled'
  trialEndsAt?: Date
  nextBillingDate?: Date
  usage: {
    tickers: number
    alerts: number
  }
}

export class SubscriptionService {
  static async getPlans(): Promise<SubscriptionPlan[]> {
    // Placeholder - would fetch from API
    return [
      {
        id: 'free',
        name: 'Free',
        price: 0,
        period: 'monthly',
        features: ['Basic filing monitoring', 'Up to 5 tickers', 'Delayed notifications'],
        limits: { tickers: 5, alerts: 10, history: 100 }
      },
      {
        id: 'pro',
        name: 'Pro',
        price: 29,
        period: 'monthly',
        features: ['Advanced analytics', 'Up to 50 tickers', 'Real-time notifications', 'Priority support'],
        limits: { tickers: 50, alerts: 100, history: 1000 }
      },
      {
        id: 'enterprise',
        name: 'Enterprise',
        price: 99,
        period: 'monthly',
        features: ['Unlimited tickers', 'Custom integrations', 'Dedicated support', 'API access'],
        limits: { tickers: -1, alerts: -1, history: -1 } // unlimited
      }
    ]
  }

  static async getCurrentSubscription(): Promise<UserSubscription> {
    // Placeholder - would fetch from API
    throw new Error('Subscription API not implemented')
  }

  static async subscribeToPlan(planId: string): Promise<UserSubscription> {
    // Placeholder - would create subscription via API
    throw new Error('Subscription API not implemented')
  }

  static async cancelSubscription(): Promise<void> {
    // Placeholder - would cancel subscription via API
    throw new Error('Subscription API not implemented')
  }

  static async updateBillingInfo(billingInfo: any): Promise<void> {
    // Placeholder - would update billing via API
    throw new Error('Subscription API not implemented')
  }

  static async getUsage(): Promise<any> {
    // Placeholder - would fetch usage from API
    throw new Error('Subscription API not implemented')
  }
}
