import React, { useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAppTheme } from '../theme';
import { useTranslation } from '../i18n';
import { useWebSocket } from '../hooks/useWebSocket';
import { usePushNotifications } from '../hooks/usePushNotifications';
import { GradientBackground } from '../components/GradientBackground';
import { StepIndicator } from '../components/StepIndicator';
import { RootStackParamList } from '../navigation/RootNavigator';

type ProgressRouteProp = RouteProp<RootStackParamList, 'Progress'>;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const STEP_ORDER = ['download', 'convert', 'transcribe', 'analyze', 'assemble'];

function getStepIndex(step: string): number {
  const idx = STEP_ORDER.findIndex((s) => step.toLowerCase().includes(s));
  return idx >= 0 ? idx : 0;
}

export function ProgressScreen() {
  const { theme } = useAppTheme();
  const { t } = useTranslation();
  const navigation = useNavigation<NavigationProp>();
  const route = useRoute<ProgressRouteProp>();
  const { taskId } = route.params;
  const { sendLocal } = usePushNotifications();

  const onComplete = useCallback(() => {
    sendLocal(t('appTitle'), t('completed'));
    navigation.replace('Result', { taskId });
  }, [taskId, navigation, sendLocal, t]);

  const onError = useCallback(
    (errorMsg: string) => {
      sendLocal(t('error'), errorMsg);
    },
    [sendLocal, t],
  );

  const { progress, isConnected } = useWebSocket({
    taskId,
    onComplete,
    onError,
  });

  const currentStep = getStepIndex(progress.step);

  return (
    <GradientBackground>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: theme.text }]}>
            {t('processing')}
          </Text>
          <View
            style={[
              styles.connectionBadge,
              { backgroundColor: isConnected ? theme.success + '30' : theme.error + '30' },
            ]}
          >
            <View
              style={[
                styles.connectionDot,
                { backgroundColor: isConnected ? theme.success : theme.error },
              ]}
            />
            <Text
              style={[
                styles.connectionText,
                { color: isConnected ? theme.success : theme.error },
              ]}
            >
              {isConnected ? t('connected') : t('connecting')}
            </Text>
          </View>
        </View>

        <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <StepIndicator
            currentStep={currentStep}
            progress={progress.progress}
            status={progress.status}
          />
        </View>

        {progress.status === 'error' && (
          <View style={[styles.errorBox, { backgroundColor: theme.error + '20', borderColor: theme.error }]}>
            <Text style={[styles.errorText, { color: theme.error }]}>
              {t('error')}: {progress.message || 'Unknown error'}
            </Text>
          </View>
        )}

        {progress.status === 'completed' && (
          <TouchableOpacity
            style={[styles.resultButton, { backgroundColor: theme.success }]}
            onPress={() => navigation.replace('Result', { taskId })}
            activeOpacity={0.7}
          >
            <Text style={styles.resultButtonText}>{t('resultTitle')}</Text>
          </TouchableOpacity>
        )}
      </View>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 60,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 30,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
  },
  connectionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  connectionText: {
    fontSize: 12,
    fontWeight: '600',
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    paddingVertical: 16,
  },
  errorBox: {
    marginTop: 20,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  errorText: {
    fontSize: 14,
    fontWeight: '600',
  },
  resultButton: {
    marginTop: 24,
    height: 50,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  resultButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
});
