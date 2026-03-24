import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Video, ResizeMode } from 'expo-av';
import * as Sharing from 'expo-sharing';
import { useRoute, RouteProp, useNavigation } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '../theme';
import { useTranslation } from '../i18n';
import { api } from '../services/api';
import { GradientBackground } from '../components/GradientBackground';
import { RootStackParamList } from '../navigation/RootNavigator';

type ResultRouteProp = RouteProp<RootStackParamList, 'Result'>;

export function ResultScreen() {
  const { theme } = useAppTheme();
  const { t } = useTranslation();
  const route = useRoute<ResultRouteProp>();
  const navigation = useNavigation();
  const { taskId } = route.params;

  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const status = await api.getTaskStatus(taskId);
        const filename = status?.result_filename || taskId;
        const stream = await api.getStreamUrl(filename);
        const download = await api.getDownloadUrl(filename);
        setStreamUrl(stream);
        setDownloadUrl(download);
      } catch {
        // Could not resolve URLs
      } finally {
        setLoading(false);
      }
    })();
  }, [taskId]);

  const handleShare = async () => {
    if (!downloadUrl) return;
    try {
      const canShare = await Sharing.isAvailableAsync();
      if (canShare) {
        await Sharing.shareAsync(downloadUrl);
      } else {
        Alert.alert(t('error'), 'Sharing is not available on this device.');
      }
    } catch (err: any) {
      Alert.alert(t('error'), err.message || String(err));
    }
  };

  if (loading) {
    return (
      <GradientBackground style={styles.centered}>
        <ActivityIndicator size="large" color={theme.primary} />
      </GradientBackground>
    );
  }

  return (
    <GradientBackground>
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} activeOpacity={0.7}>
            <Ionicons name="arrow-back" size={24} color={theme.text} />
          </TouchableOpacity>
          <Text style={[styles.title, { color: theme.text }]}>
            {t('resultTitle')}
          </Text>
          <View style={{ width: 24 }} />
        </View>

        {streamUrl && (
          <View style={[styles.videoContainer, { backgroundColor: theme.card, borderColor: theme.border }]}>
            <Video
              source={{ uri: streamUrl }}
              style={styles.video}
              useNativeControls
              resizeMode={ResizeMode.CONTAIN}
              shouldPlay={false}
            />
          </View>
        )}

        <View style={styles.actions}>
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: theme.primary }]}
            onPress={handleShare}
            activeOpacity={0.7}
          >
            <Ionicons name="share-outline" size={20} color="#fff" style={styles.actionIcon} />
            <Text style={styles.actionButtonText}>{t('share')}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: theme.accent }]}
            onPress={() => {
              if (downloadUrl) {
                Alert.alert(t('download'), downloadUrl);
              }
            }}
            activeOpacity={0.7}
          >
            <Ionicons name="download-outline" size={20} color="#fff" style={styles.actionIcon} />
            <Text style={styles.actionButtonText}>{t('download')}</Text>
          </TouchableOpacity>
        </View>

        <View style={[styles.infoCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[styles.infoLabel, { color: theme.textSecondary }]}>
            Task ID
          </Text>
          <Text style={[styles.infoValue, { color: theme.text }]}>
            {taskId}
          </Text>
        </View>
      </View>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  container: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 60,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
  },
  videoContainer: {
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: 24,
  },
  video: {
    width: '100%',
    height: 220,
  },
  actions: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  actionButton: {
    flex: 1,
    height: 48,
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionIcon: {
    marginRight: 8,
  },
  actionButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
  infoCard: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  infoLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '500',
  },
});
