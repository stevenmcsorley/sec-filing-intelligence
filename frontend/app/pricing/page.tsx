// app/pricing/page.tsx
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Check, X, Zap, Shield, BarChart3, Clock, Users, Star } from "lucide-react"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"

const plans = [
  {
    name: "Free",
    price: 0,
    period: "forever",
    description: "Perfect for getting started with SEC filing monitoring",
    features: [
      { text: "Up to 5 tickers", included: true },
      { text: "Basic filing alerts", included: true },
      { text: "Delayed notifications (20+ min)", included: true },
      { text: "Limited filing history", included: true },
      { text: "Basic analysis", included: true },
      { text: "Real-time alerts", included: false },
      { text: "Advanced analytics", included: false },
      { text: "Price correlation data", included: false },
      { text: "Export capabilities", included: false },
      { text: "Priority support", included: false }
    ],
    cta: "Get Started",
    popular: false,
    icon: <Users className="h-6 w-6" />
  },
  {
    name: "Pro",
    price: 29,
    period: "month",
    description: "For serious investors who need comprehensive filing intelligence",
    features: [
      { text: "Up to 200 tickers", included: true },
      { text: "Real-time alerts", included: true },
      { text: "Advanced AI analysis", included: true },
      { text: "Full filing history", included: true },
      { text: "Price correlation analysis", included: true },
      { text: "Insider trading insights", included: true },
      { text: "Export to CSV/PDF", included: true },
      { text: "Custom watchlists", included: true },
      { text: "Email notifications", included: true },
      { text: "Priority support", included: true }
    ],
    cta: "Start Pro Trial",
    popular: true,
    icon: <Zap className="h-6 w-6" />
  },
  {
    name: "Enterprise",
    price: 99,
    period: "month",
    description: "For teams and organizations requiring advanced features",
    features: [
      { text: "Unlimited tickers", included: true },
      { text: "Team collaboration", included: true },
      { text: "Custom integrations", included: true },
      { text: "API access", included: true },
      { text: "White-label options", included: true },
      { text: "Advanced reporting", included: true },
      { text: "Dedicated support", included: true },
      { text: "Custom alerts", included: true },
      { text: "Data retention", included: true },
      { text: "SLA guarantees", included: true }
    ],
    cta: "Contact Sales",
    popular: false,
    icon: <Shield className="h-6 w-6" />
  }
]

const features = [
  {
    icon: <Zap className="h-8 w-8 text-yellow-500" />,
    title: "Real-time Alerts",
    description: "Get instant notifications when important filings are published, with AI-powered impact analysis."
  },
  {
    icon: <BarChart3 className="h-8 w-8 text-blue-500" />,
    title: "Advanced Analytics",
    description: "Deep insights into filing patterns, price correlations, and market-moving events."
  },
  {
    icon: <Shield className="h-8 w-8 text-green-500" />,
    title: "Secure & Compliant",
    description: "Enterprise-grade security with role-based access control and audit trails."
  },
  {
    icon: <Clock className="h-8 w-8 text-purple-500" />,
    title: "Lightning Fast",
    description: "Process thousands of filings daily with sub-second analysis and delivery."
  }
]

export default function PricingPage() {
  return (
    <ProtectedRoute>
      <div className="container mx-auto py-16">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold mb-4">Choose Your Plan</h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Get comprehensive SEC filing intelligence with AI-powered analysis. 
            Start free and upgrade as your needs grow.
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
          {plans.map((plan) => (
            <Card 
              key={plan.name} 
              className={`relative ${plan.popular ? 'border-primary shadow-lg scale-105' : ''}`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                  <Badge className="bg-primary text-primary-foreground px-4 py-1">
                    <Star className="h-3 w-3 mr-1" />
                    Most Popular
                  </Badge>
                </div>
              )}
              
              <CardHeader className="text-center pb-4">
                <div className="flex justify-center mb-4">
                  <div className={`p-3 rounded-full ${plan.popular ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                    {plan.icon}
                  </div>
                </div>
                <CardTitle className="text-2xl">{plan.name}</CardTitle>
                <div className="mt-4">
                  <span className="text-4xl font-bold">${plan.price}</span>
                  <span className="text-muted-foreground">/{plan.period}</span>
                </div>
                <p className="text-sm text-muted-foreground mt-2">{plan.description}</p>
              </CardHeader>
              
              <CardContent>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature, index) => (
                    <li key={index} className="flex items-center gap-3">
                      {feature.included ? (
                        <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                      ) : (
                        <X className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      )}
                      <span className={feature.included ? '' : 'text-muted-foreground'}>
                        {feature.text}
                      </span>
                    </li>
                  ))}
                </ul>
                
                <Button 
                  className={`w-full ${plan.popular ? 'bg-primary hover:bg-primary/90' : ''}`}
                  variant={plan.popular ? 'default' : 'outline'}
                >
                  {plan.cta}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Features Section */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold text-center mb-12">Why Choose SEC Filing Intelligence?</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <Card key={index} className="text-center">
                <CardContent className="pt-6">
                  <div className="flex justify-center mb-4">
                    {feature.icon}
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                  <p className="text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* FAQ Section */}
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Frequently Asked Questions</h2>
          <div className="space-y-6">
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold mb-2">What&apos;s included in the free plan?</h3>
                <p className="text-muted-foreground">
                  The free plan includes basic filing monitoring for up to 5 tickers, 
                  delayed notifications, and limited filing history. Perfect for getting started.
                </p>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold mb-2">How does the AI analysis work?</h3>
                <p className="text-muted-foreground">
                  Our AI analyzes SEC filings to identify material events, insider transactions, 
                  and market-moving information. It uses rule-based pre-processing to reduce costs 
                  and improve accuracy.
                </p>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold mb-2">Can I change plans anytime?</h3>
                <p className="text-muted-foreground">
                  Yes, you can upgrade or downgrade your plan at any time. Changes take effect 
                  immediately, and we&apos;ll prorate any billing differences.
                </p>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold mb-2">Is there a trial period?</h3>
                <p className="text-muted-foreground">
                  Yes, Pro plans come with a 14-day free trial. No credit card required to start, 
                  and you can cancel anytime during the trial period.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* CTA Section */}
        <div className="text-center mt-16">
          <Card className="max-w-2xl mx-auto">
            <CardContent className="pt-8 pb-8">
              <h2 className="text-2xl font-bold mb-4">Ready to Get Started?</h2>
              <p className="text-muted-foreground mb-6">
                Join thousands of investors who rely on SEC Filing Intelligence for 
                market-moving insights and real-time alerts.
              </p>
              <div className="flex gap-4 justify-center">
                <Button size="lg">Start Free Trial</Button>
                <Button variant="outline" size="lg">Contact Sales</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </ProtectedRoute>
  )
}
