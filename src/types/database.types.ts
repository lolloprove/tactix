export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      match_ai_briefs: {
        Row: {
          brief_type: Database["public"]["Enums"]["brief_type"]
          generated_at: string
          id: number
          key_edges_json: Json
          match_id: number
          matchups_json: Json
          model: string | null
          player_observations_json: Json
          tactical_summary: string
          x_factors_json: Json
        }
        Insert: {
          brief_type: Database["public"]["Enums"]["brief_type"]
          generated_at?: string
          id?: never
          key_edges_json?: Json
          match_id: number
          matchups_json?: Json
          model?: string | null
          player_observations_json?: Json
          tactical_summary: string
          x_factors_json?: Json
        }
        Update: {
          brief_type?: Database["public"]["Enums"]["brief_type"]
          generated_at?: string
          id?: never
          key_edges_json?: Json
          match_id?: number
          matchups_json?: Json
          model?: string | null
          player_observations_json?: Json
          tactical_summary?: string
          x_factors_json?: Json
        }
        Relationships: [
          {
            foreignKeyName: "match_ai_briefs_match_id_fkey"
            columns: ["match_id"]
            isOneToOne: false
            referencedRelation: "matches"
            referencedColumns: ["id"]
          },
        ]
      }
      matches: {
        Row: {
          away_goals: number | null
          away_team_id: number
          away_xg: number | null
          fotmob_id: number | null
          home_goals: number | null
          home_team_id: number
          home_xg: number | null
          id: number
          kickoff_at: string
          round: number
          season: string
          sofascore_id: number | null
          status: Database["public"]["Enums"]["match_status"]
          understat_id: number | null
          updated_at: string
        }
        Insert: {
          away_goals?: number | null
          away_team_id: number
          away_xg?: number | null
          fotmob_id?: number | null
          home_goals?: number | null
          home_team_id: number
          home_xg?: number | null
          id?: never
          kickoff_at: string
          round: number
          season: string
          sofascore_id?: number | null
          status?: Database["public"]["Enums"]["match_status"]
          understat_id?: number | null
          updated_at?: string
        }
        Update: {
          away_goals?: number | null
          away_team_id: number
          away_xg?: number | null
          fotmob_id?: number | null
          home_goals?: number | null
          home_team_id: number
          home_xg?: number | null
          id?: never
          kickoff_at?: string
          round: number
          season: string
          sofascore_id?: number | null
          status?: Database["public"]["Enums"]["match_status"]
          understat_id?: number | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "matches_away_team_id_fkey"
            columns: ["away_team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "matches_away_team_id_fkey"
            columns: ["away_team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
          {
            foreignKeyName: "matches_home_team_id_fkey"
            columns: ["home_team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "matches_home_team_id_fkey"
            columns: ["home_team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
        ]
      }
      player_conditional_splits: {
        Row: {
          computed_at: string
          condition_type: Database["public"]["Enums"]["player_condition_type"]
          condition_value: string
          confidence: Database["public"]["Enums"]["confidence_level"] | null
          dribbles_delta: number | null
          duels_delta: number | null
          id: number
          player_id: number
          rating_delta: number | null
          sample_minutes: number
          season: string
        }
        Insert: {
          computed_at?: string
          condition_type: Database["public"]["Enums"]["player_condition_type"]
          condition_value: string
          confidence?: Database["public"]["Enums"]["confidence_level"] | null
          dribbles_delta?: number | null
          duels_delta?: number | null
          id?: never
          player_id: number
          rating_delta?: number | null
          sample_minutes: number
          season: string
        }
        Update: {
          computed_at?: string
          condition_type?: Database["public"]["Enums"]["player_condition_type"]
          condition_value?: string
          confidence?: Database["public"]["Enums"]["confidence_level"] | null
          dribbles_delta?: number | null
          duels_delta?: number | null
          id?: never
          player_id?: number
          rating_delta?: number | null
          sample_minutes?: number
          season: string
        }
        Relationships: [
          {
            foreignKeyName: "player_conditional_splits_player_id_fkey"
            columns: ["player_id"]
            isOneToOne: false
            referencedRelation: "players"
            referencedColumns: ["id"]
          },
        ]
      }
      player_match_stats: {
        Row: {
          avg_x: number | null
          avg_y: number | null
          dribbles_past: number | null
          dribbles_won: number | null
          duels_lost: number | null
          duels_won: number | null
          match_id: number
          minutes: number
          opponent_id: number
          player_id: number
          position_played: Database["public"]["Enums"]["player_position"] | null
          progressive_actions: number | null
          rating: number | null
          team_id: number
          xa: number | null
          xg: number | null
          zone_corridor: Database["public"]["Enums"]["zone_corridor"] | null
        }
        Insert: {
          avg_x?: number | null
          avg_y?: number | null
          dribbles_past?: number | null
          dribbles_won?: number | null
          duels_lost?: number | null
          duels_won?: number | null
          match_id: number
          minutes: number
          opponent_id: number
          player_id: number
          position_played?:
            | Database["public"]["Enums"]["player_position"]
            | null
          progressive_actions?: number | null
          rating?: number | null
          team_id: number
          xa?: number | null
          xg?: number | null
          zone_corridor?: Database["public"]["Enums"]["zone_corridor"] | null
        }
        Update: {
          avg_x?: number | null
          avg_y?: number | null
          dribbles_past?: number | null
          dribbles_won?: number | null
          duels_lost?: number | null
          duels_won?: number | null
          match_id?: number
          minutes?: number
          opponent_id?: number
          player_id?: number
          position_played?:
            | Database["public"]["Enums"]["player_position"]
            | null
          progressive_actions?: number | null
          rating?: number | null
          team_id?: number
          xa?: number | null
          xg?: number | null
          zone_corridor?: Database["public"]["Enums"]["zone_corridor"] | null
        }
        Relationships: [
          {
            foreignKeyName: "player_match_stats_match_id_fkey"
            columns: ["match_id"]
            isOneToOne: false
            referencedRelation: "matches"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "player_match_stats_opponent_id_fkey"
            columns: ["opponent_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "player_match_stats_opponent_id_fkey"
            columns: ["opponent_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
          {
            foreignKeyName: "player_match_stats_player_id_fkey"
            columns: ["player_id"]
            isOneToOne: false
            referencedRelation: "players"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "player_match_stats_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "player_match_stats_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
        ]
      }
      players: {
        Row: {
          archetype_primary:
            | Database["public"]["Enums"]["player_archetype"]
            | null
          archetype_scores_json: Json
          archetype_secondary:
            | Database["public"]["Enums"]["player_archetype"]
            | null
          fotmob_id: number | null
          id: number
          minutes_total: number
          name: string
          primary_position: Database["public"]["Enums"]["player_position"]
          radar_percentiles_json: Json | null
          sofascore_id: number | null
          team_id: number | null
          understat_id: number | null
          updated_at: string
        }
        Insert: {
          archetype_primary?:
            | Database["public"]["Enums"]["player_archetype"]
            | null
          archetype_scores_json?: Json
          archetype_secondary?:
            | Database["public"]["Enums"]["player_archetype"]
            | null
          fotmob_id?: number | null
          id?: never
          minutes_total?: number
          name: string
          primary_position: Database["public"]["Enums"]["player_position"]
          radar_percentiles_json?: Json | null
          sofascore_id?: number | null
          team_id?: number | null
          understat_id?: number | null
          updated_at?: string
        }
        Update: {
          archetype_primary?:
            | Database["public"]["Enums"]["player_archetype"]
            | null
          archetype_scores_json?: Json
          archetype_secondary?:
            | Database["public"]["Enums"]["player_archetype"]
            | null
          fotmob_id?: number | null
          id?: never
          minutes_total?: number
          name: string
          primary_position: Database["public"]["Enums"]["player_position"]
          radar_percentiles_json?: Json | null
          sofascore_id?: number | null
          team_id?: number | null
          understat_id?: number | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "players_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "players_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
        ]
      }
      team_conditional_splits: {
        Row: {
          computed_at: string
          condition_type: Database["public"]["Enums"]["team_condition_type"]
          condition_value: string
          confidence: Database["public"]["Enums"]["confidence_level"] | null
          dribbles_conceded_delta: number | null
          id: number
          sample_matches: number
          season: string
          team_id: number
          xg_delta: number | null
          xga_delta: number | null
        }
        Insert: {
          computed_at?: string
          condition_type: Database["public"]["Enums"]["team_condition_type"]
          condition_value: string
          confidence?: Database["public"]["Enums"]["confidence_level"] | null
          dribbles_conceded_delta?: number | null
          id?: never
          sample_matches: number
          season: string
          team_id: number
          xg_delta?: number | null
          xga_delta?: number | null
        }
        Update: {
          computed_at?: string
          condition_type?: Database["public"]["Enums"]["team_condition_type"]
          condition_value?: string
          confidence?: Database["public"]["Enums"]["confidence_level"] | null
          dribbles_conceded_delta?: number | null
          id?: never
          sample_matches?: number
          season?: string
          team_id?: number
          xg_delta?: number | null
          xga_delta?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "team_conditional_splits_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "team_conditional_splits_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
        ]
      }
      team_how_to_beat: {
        Row: {
          ai_playbook_text: string | null
          season: string
          team_id: number
          through_round: number | null
          updated_at: string
          vulnerabilities_json: Json
        }
        Insert: {
          ai_playbook_text?: string | null
          season: string
          team_id: number
          through_round?: number | null
          updated_at?: string
          vulnerabilities_json?: Json
        }
        Update: {
          ai_playbook_text?: string | null
          season?: string
          team_id?: number
          through_round?: number | null
          updated_at?: string
          vulnerabilities_json?: Json
        }
        Relationships: [
          {
            foreignKeyName: "team_how_to_beat_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "team_how_to_beat_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
        ]
      }
      team_match_tactics: {
        Row: {
          attack_bias_center: number | null
          attack_bias_left: number | null
          attack_bias_right: number | null
          avg_def_line_y: number | null
          back_line_count: number | null
          baseline_formation: string | null
          dribbles_zones_json: Json | null
          field_tilt: number | null
          formation: string | null
          is_tactical_shift: boolean
          match_id: number
          possession: number | null
          ppda: number | null
          shift_reason: string | null
          team_id: number
          xga_zones_json: Json | null
        }
        Insert: {
          attack_bias_center?: number | null
          attack_bias_left?: number | null
          attack_bias_right?: number | null
          avg_def_line_y?: number | null
          back_line_count?: number | null
          baseline_formation?: string | null
          dribbles_zones_json?: Json | null
          field_tilt?: number | null
          formation?: string | null
          is_tactical_shift?: boolean
          match_id: number
          possession?: number | null
          ppda?: number | null
          shift_reason?: string | null
          team_id: number
          xga_zones_json?: Json | null
        }
        Update: {
          attack_bias_center?: number | null
          attack_bias_left?: number | null
          attack_bias_right?: number | null
          avg_def_line_y?: number | null
          back_line_count?: number | null
          baseline_formation?: string | null
          dribbles_zones_json?: Json | null
          field_tilt?: number | null
          formation?: string | null
          is_tactical_shift?: boolean
          match_id?: number
          possession?: number | null
          ppda?: number | null
          shift_reason?: string | null
          team_id?: number
          xga_zones_json?: Json | null
        }
        Relationships: [
          {
            foreignKeyName: "team_match_tactics_match_id_fkey"
            columns: ["match_id"]
            isOneToOne: false
            referencedRelation: "matches"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "team_match_tactics_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "team_match_tactics_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
        ]
      }
      teams: {
        Row: {
          fotmob_id: number | null
          id: number
          logo_url: string | null
          name: string
          short_name: string
          slug: string
          sofascore_id: number | null
          understat_id: number | null
          updated_at: string
        }
        Insert: {
          fotmob_id?: number | null
          id?: never
          logo_url?: string | null
          name: string
          short_name: string
          slug: string
          sofascore_id?: number | null
          understat_id?: number | null
          updated_at?: string
        }
        Update: {
          fotmob_id?: number | null
          id?: never
          logo_url?: string | null
          name: string
          short_name: string
          slug: string
          sofascore_id?: number | null
          understat_id?: number | null
          updated_at?: string
        }
        Relationships: []
      }
    }
    Views: {
      v_league_tactical_scatter: {
        Row: {
          avg_def_line_y: number | null
          avg_field_tilt: number | null
          avg_possession: number | null
          avg_ppda: number | null
          confidence: Database["public"]["Enums"]["confidence_level"] | null
          expected_points: number | null
          ga_minus_xga: number | null
          goals_against: number | null
          goals_for: number | null
          goals_minus_xg: number | null
          league_avg_def_line_y: number | null
          league_avg_ppda: number | null
          matches_played: number | null
          points: number | null
          points_variance: number | null
          sample_matches: number | null
          season: string | null
          short_name: string | null
          slug: string | null
          team_id: number | null
          team_name: string | null
          xg_against: number | null
          xg_for: number | null
        }
        Relationships: []
      }
      v_team_shift_windows: {
        Row: {
          after_from_round: number | null
          after_matches: number | null
          after_to_round: number | null
          after_xg_diff: number | null
          baseline_formation: string | null
          before_from_round: number | null
          before_matches: number | null
          before_to_round: number | null
          before_xg_diff: number | null
          confidence: Database["public"]["Enums"]["confidence_level"] | null
          formation: string | null
          match_id: number | null
          season: string | null
          shift_reason: string | null
          shift_round: number | null
          team_id: number | null
          xg_diff_delta: number | null
        }
        Relationships: [
          {
            foreignKeyName: "team_match_tactics_match_id_fkey"
            columns: ["match_id"]
            isOneToOne: false
            referencedRelation: "matches"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "team_match_tactics_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "team_match_tactics_team_id_fkey"
            columns: ["team_id"]
            isOneToOne: false
            referencedRelation: "v_league_tactical_scatter"
            referencedColumns: ["team_id"]
          },
        ]
      }
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      brief_type: "pre_match" | "post_match"
      confidence_level: "low" | "medium" | "high"
      match_status:
        | "scheduled"
        | "live"
        | "finished"
        | "postponed"
        | "cancelled"
      player_archetype:
        | "portiere_classico"
        | "portiere_libero"
        | "braccetto"
        | "centrale_marcatore"
        | "centrale_impostazione"
        | "terzino_difensivo"
        | "terzino_spinta"
        | "terzino_invertito"
        | "quinto"
        | "regista"
        | "mediano_incontrista"
        | "mezzala"
        | "box_to_box"
        | "trequartista"
        | "ala_dribblatrice"
        | "ala_inversa"
        | "prima_punta"
        | "falso_nove"
        | "attaccante_profondita"
        | "seconda_punta"
      player_condition_type:
        | "vs_defender_archetype"
        | "vs_attacker_archetype"
        | "vs_line_height"
        | "vs_formation"
      player_position:
        | "GK"
        | "CB"
        | "LB"
        | "RB"
        | "LWB"
        | "RWB"
        | "DM"
        | "CM"
        | "AM"
        | "LW"
        | "RW"
        | "ST"
      team_condition_type:
        | "vs_formation"
        | "vs_back_line"
        | "vs_high_line"
        | "vs_archetype"
      zone_corridor: "left" | "left_half" | "center" | "right_half" | "right"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      brief_type: ["pre_match", "post_match"],
      confidence_level: ["low", "medium", "high"],
      match_status: ["scheduled", "live", "finished", "postponed", "cancelled"],
      player_archetype: [
        "portiere_classico",
        "portiere_libero",
        "braccetto",
        "centrale_marcatore",
        "centrale_impostazione",
        "terzino_difensivo",
        "terzino_spinta",
        "terzino_invertito",
        "quinto",
        "regista",
        "mediano_incontrista",
        "mezzala",
        "box_to_box",
        "trequartista",
        "ala_dribblatrice",
        "ala_inversa",
        "prima_punta",
        "falso_nove",
        "attaccante_profondita",
        "seconda_punta",
      ],
      player_condition_type: [
        "vs_defender_archetype",
        "vs_attacker_archetype",
        "vs_line_height",
        "vs_formation",
      ],
      player_position: [
        "GK",
        "CB",
        "LB",
        "RB",
        "LWB",
        "RWB",
        "DM",
        "CM",
        "AM",
        "LW",
        "RW",
        "ST",
      ],
      team_condition_type: [
        "vs_formation",
        "vs_back_line",
        "vs_high_line",
        "vs_archetype",
      ],
      zone_corridor: ["left", "left_half", "center", "right_half", "right"],
    },
  },
} as const
