// =====================================================
// MongoDB practice queries (paste into mongosh or the Compass shell)
// Run the AI analysis first so the collections have documents.
// =====================================================

db = db.getSiblingDB("supermart")

// ---------- Basic queries ----------

// All forecasts, highest demand first, only a few fields
db.demand_forecasts.find({}, {_id: 0, sku: 1, name: 1, forecast_total: 1}).sort({forecast_total: -1})

// Products the AI says to reorder urgently
db.demand_forecasts.find({"restock.urgency": {$in: ["Critical", "High"]}}, {_id: 0, name: 1, restock: 1})

// Recommendations for one product
db.recommendations.findOne({sku: "P006"}, {_id: 0, name: 1, recommended: 1})

// Customers in the Champion segment
db.customer_behavior.find({segment: "Champion"}, {_id: 0, name: 1, total_spent: 1, visits: 1})

// Count documents in each collection
db.demand_forecasts.countDocuments()
db.recommendations.countDocuments()
db.customer_behavior.countDocuments()
db.ai_logs.countDocuments()

// ---------- Aggregation pipelines (same ones the app runs) ----------

// Highest expected demand (next 7 days)  ($project, $sort, $limit)
db.demand_forecasts.aggregate([
  {
    "$project": {
      "_id": 0,
      "sku": 1,
      "name": 1,
      "current_stock": 1,
      "forecast_total": 1
    }
  },
  {
    "$sort": {
      "forecast_total": -1
    }
  },
  {
    "$limit": 5
  }
])

// Products to reorder, by urgency  ($match, $group, $sort)
db.demand_forecasts.aggregate([
  {
    "$match": {
      "restock.urgency": {
        "$in": [
          "Critical",
          "High",
          "Medium"
        ]
      }
    }
  },
  {
    "$group": {
      "_id": "$restock.urgency",
      "products": {
        "$sum": 1
      },
      "units_to_order": {
        "$sum": "$restock.reorder_qty"
      },
      "items": {
        "$push": "$name"
      }
    }
  },
  {
    "$sort": {
      "units_to_order": -1
    }
  }
])

// Forecast per day (unwind the daily array)  ($unwind, $group, $sort)
db.demand_forecasts.aggregate([
  {
    "$unwind": "$forecast"
  },
  {
    "$group": {
      "_id": "$forecast.date",
      "expected_units": {
        "$sum": "$forecast.qty"
      }
    }
  },
  {
    "$sort": {
      "_id": 1
    }
  }
])

// Customer segments summary  ($group, $project, $sort)
db.customer_behavior.aggregate([
  {
    "$group": {
      "_id": "$segment",
      "customers": {
        "$sum": 1
      },
      "avg_spent": {
        "$avg": "$total_spent"
      },
      "avg_visits": {
        "$avg": "$visits"
      }
    }
  },
  {
    "$project": {
      "segment": "$_id",
      "_id": 0,
      "customers": 1,
      "avg_spent": {
        "$round": [
          "$avg_spent",
          0
        ]
      },
      "avg_visits": {
        "$round": [
          "$avg_visits",
          1
        ]
      }
    }
  },
  {
    "$sort": {
      "avg_spent": -1
    }
  }
])

// Strongest product pairs (lift)  ($unwind, $match, $project, $sort, $limit)
db.recommendations.aggregate([
  {
    "$unwind": "$recommended"
  },
  {
    "$match": {
      "recommended.lift": {
        "$gt": 1.2
      }
    }
  },
  {
    "$project": {
      "_id": 0,
      "bought": "$name",
      "also_bought": "$recommended.name",
      "confidence": "$recommended.confidence",
      "lift": "$recommended.lift"
    }
  },
  {
    "$sort": {
      "lift": -1
    }
  },
  {
    "$limit": 10
  }
])

// Reorder items with their recommendations ($lookup join)  ($match, $lookup, $unwind, $project, $sort)
db.demand_forecasts.aggregate([
  {
    "$match": {
      "restock.reorder_qty": {
        "$gt": 0
      }
    }
  },
  {
    "$lookup": {
      "from": "recommendations",
      "localField": "product_id",
      "foreignField": "product_id",
      "as": "rec"
    }
  },
  {
    "$unwind": {
      "path": "$rec",
      "preserveNullAndEmptyArrays": true
    }
  },
  {
    "$project": {
      "_id": 0,
      "name": 1,
      "reorder_qty": "$restock.reorder_qty",
      "also_restock": "$rec.recommended.name"
    }
  },
  {
    "$sort": {
      "reorder_qty": -1
    }
  }
])

// AI activity log  ($group, $sort)
db.ai_logs.aggregate([
  {
    "$group": {
      "_id": "$action",
      "times_run": {
        "$sum": 1
      },
      "avg_ms": {
        "$avg": "$duration_ms"
      },
      "last_run": {
        "$max": "$timestamp"
      }
    }
  },
  {
    "$sort": {
      "last_run": -1
    }
  }
])
