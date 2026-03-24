import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAppTheme } from '../theme';
import { useTranslation } from '../i18n';
import { api } from '../services/api';
import { GradientBackground } from '../components/GradientBackground';
import { SourceButton } from '../components/SourceButton';
import { RootStackParamList } from '../navigation/RootNavigator';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export function HomeScreen() {
  const { theme } = useAppTheme();
  const { t } = useTranslation();
  const navigation = useNavigation<NavigationProp>();

  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showUrlInput, setShowUrlInput] = useState(false);

  const handleFilePick = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['video/*', 'audio/*'],
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets?.length) return;

      const file = result.assets[0];
      setIsLoading(true);

      try {
        const data = await api.uploadFile(file.uri, file.name);
        if (data.task_id) {
          navigation.navigate('Progress', { taskId: data.task_id });
        }
      } catch (err: any) {
        Alert.alert(t('error'), err.message || String(err));
      } finally {
        setIsLoading(false);
      }
    } catch (err: any) {
      Alert.alert(t('error'), err.message || String(err));
    }
  };

  const handleUrlSubmit = async () => {
    if (!url.trim()) return;

    setIsLoading(true);
    try {
      const data = await api.submitUrl(url.trim());
      if (data.task_id) {
        setUrl('');
        setShowUrlInput(false);
        navigation.navigate('Progress', { taskId: data.task_id });
      }
    } catch (err: any) {
      Alert.alert(t('error'), err.message || String(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleCamera = () => {
    Alert.alert(t('tabCamera'), 'Camera recording is coming soon.');
  };

  if (isLoading) {
    return (
      <GradientBackground style={styles.centered}>
        <ActivityIndicator size="large" color={theme.primary} />
        <Text style={[styles.loadingText, { color: theme.text }]}>
          {t('processing')}
        </Text>
      </GradientBackground>
    );
  }

  return (
    <GradientBackground>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <Text style={[styles.title, { color: theme.primary }]}>
              {t('appTitle')}
            </Text>
          </View>

          <View style={styles.buttonsRow}>
            <SourceButton
              icon="document"
              label={t('tabFile')}
              onPress={handleFilePick}
              color={theme.primary}
            />
            <SourceButton
              icon="link"
              label={t('tabUrl')}
              onPress={() => setShowUrlInput(!showUrlInput)}
              color={theme.accent}
            />
            <SourceButton
              icon="videocam"
              label={t('tabCamera')}
              onPress={handleCamera}
              color={theme.success}
            />
          </View>

          {showUrlInput && (
            <View style={styles.urlSection}>
              <TextInput
                style={[
                  styles.urlInput,
                  {
                    backgroundColor: theme.inputBackground,
                    color: theme.text,
                    borderColor: theme.border,
                  },
                ]}
                placeholder={t('urlPlaceholder')}
                placeholderTextColor={theme.textSecondary}
                value={url}
                onChangeText={setUrl}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                returnKeyType="go"
                onSubmitEditing={handleUrlSubmit}
              />
              <TouchableOpacity
                style={[styles.processButton, { backgroundColor: theme.primary }]}
                onPress={handleUrlSubmit}
                activeOpacity={0.7}
              >
                <Text style={styles.processButtonText}>{t('btnProcess')}</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 20,
    paddingVertical: 40,
  },
  header: {
    alignItems: 'center',
    marginBottom: 40,
  },
  title: {
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: 1,
  },
  buttonsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 24,
  },
  urlSection: {
    marginTop: 8,
  },
  urlInput: {
    height: 50,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 15,
    marginBottom: 12,
  },
  processButton: {
    height: 50,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  processButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    fontWeight: '600',
  },
});
