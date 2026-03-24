import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '../theme';
import { useTranslation } from '../i18n';

interface StepIndicatorProps {
  currentStep: number;
  progress: number;
  status: 'pending' | 'running' | 'completed' | 'error';
}

const STEP_KEYS = [
  'stepDownload',
  'stepConvert',
  'stepTranscribe',
  'stepAnalyze',
  'stepAssemble',
] as const;

export function StepIndicator({ currentStep, progress, status }: StepIndicatorProps) {
  const { theme } = useAppTheme();
  const { t } = useTranslation();
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (status === 'running') {
      const animation = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.2,
            duration: 600,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 600,
            useNativeDriver: true,
          }),
        ]),
      );
      animation.start();
      return () => animation.stop();
    } else {
      pulseAnim.setValue(1);
    }
  }, [status, pulseAnim]);

  const getStepState = (index: number): 'completed' | 'active' | 'pending' => {
    if (status === 'completed') return 'completed';
    if (index < currentStep) return 'completed';
    if (index === currentStep) return 'active';
    return 'pending';
  };

  return (
    <View style={styles.container}>
      {STEP_KEYS.map((key, index) => {
        const stepState = getStepState(index);
        const isLast = index === STEP_KEYS.length - 1;

        return (
          <View key={key} style={styles.stepRow}>
            <View style={styles.indicatorColumn}>
              {stepState === 'completed' ? (
                <View
                  style={[
                    styles.circle,
                    { backgroundColor: theme.success, borderColor: theme.success },
                  ]}
                >
                  <Ionicons name="checkmark" size={18} color="#fff" />
                </View>
              ) : stepState === 'active' ? (
                <Animated.View
                  style={[
                    styles.circle,
                    {
                      backgroundColor: theme.primary,
                      borderColor: theme.primary,
                      transform: [{ scale: pulseAnim }],
                    },
                  ]}
                >
                  <Text style={styles.circleText}>{Math.round(progress)}%</Text>
                </Animated.View>
              ) : (
                <View
                  style={[
                    styles.circle,
                    {
                      backgroundColor: 'transparent',
                      borderColor: theme.border,
                    },
                  ]}
                >
                  <Text style={[styles.circleNumber, { color: theme.textSecondary }]}>
                    {index + 1}
                  </Text>
                </View>
              )}

              {!isLast && (
                <View
                  style={[
                    styles.line,
                    {
                      backgroundColor:
                        stepState === 'completed' ? theme.success : theme.border,
                    },
                  ]}
                />
              )}
            </View>

            <View style={styles.labelColumn}>
              <Text
                style={[
                  styles.stepLabel,
                  {
                    color:
                      stepState === 'completed'
                        ? theme.success
                        : stepState === 'active'
                        ? theme.text
                        : theme.textSecondary,
                    fontWeight: stepState === 'active' ? '700' : '400',
                  },
                ]}
              >
                {t(key)}
              </Text>
              {stepState === 'active' && (
                <View style={[styles.progressBar, { backgroundColor: theme.border }]}>
                  <View
                    style={[
                      styles.progressFill,
                      {
                        backgroundColor: theme.primary,
                        width: `${Math.min(progress, 100)}%`,
                      },
                    ]}
                  />
                </View>
              )}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  indicatorColumn: {
    alignItems: 'center',
    width: 40,
  },
  circle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  circleText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  circleNumber: {
    fontSize: 14,
    fontWeight: '600',
  },
  line: {
    width: 2,
    height: 30,
    marginVertical: 2,
  },
  labelColumn: {
    flex: 1,
    paddingLeft: 12,
    paddingTop: 6,
    minHeight: 68,
  },
  stepLabel: {
    fontSize: 16,
  },
  progressBar: {
    height: 4,
    borderRadius: 2,
    marginTop: 8,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
});
