import tensorflow as tf
import re
from collections import Counter
import string


def create_batch(filename, config, test=False):
    if test:
        queue = tf.train.string_input_producer([filename], num_epochs=1)
        min_after_deque = 0
    else:
        queue = tf.train.string_input_producer([filename])
        min_after_deque = config.min_after_deque

    para_limit = config.para_limit
    ques_limit = config.ques_limit
    char_limit = config.char_limit
    num_threads = config.num_threads
    batch_size = config.batch_size
    reader = tf.TFRecordReader()
    _, serialized_example = reader.read(queue)
    features = tf.parse_single_example(serialized_example,
                                       features={
                                           "context_idxs": tf.FixedLenFeature([], tf.string),
                                           "ques_idxs": tf.FixedLenFeature([], tf.string),
                                           "context_char_idxs": tf.FixedLenFeature([], tf.string),
                                           "ques_char_idxs": tf.FixedLenFeature([], tf.string),
                                           "y1": tf.FixedLenFeature([], tf.string),
                                           "y2": tf.FixedLenFeature([], tf.string),
                                           "id": tf.FixedLenFeature([], tf.int64)
                                       })
    context_idxs = tf.reshape(tf.decode_raw(
        features["context_idxs"], tf.int32), [para_limit])
    ques_idxs = tf.reshape(tf.decode_raw(
        features["ques_idxs"], tf.int32), [ques_limit])
    context_char_idxs = tf.reshape(tf.decode_raw(
        features["context_char_idxs"], tf.int32), [para_limit, char_limit])
    ques_char_idxs = tf.reshape(tf.decode_raw(
        features["ques_char_idxs"], tf.int32), [ques_limit, char_limit])
    y1 = tf.reshape(tf.decode_raw(features["y1"], tf.float32), [para_limit])
    y2 = tf.reshape(tf.decode_raw(features["y2"], tf.float32), [para_limit])
    qa_id = features["id"]
    return tf.train.shuffle_batch([context_idxs, ques_idxs, context_char_idxs, ques_char_idxs, y1, y2, qa_id], batch_size=batch_size,
                                  num_threads=num_threads, min_after_dequeue=min_after_deque, capacity=config.capacity)


def convert_tokens(eval_file, qa_id, pp1, pp2):
    answer_dict = {}
    for qid, p1, p2 in zip(qa_id, pp1, pp2):
        context = eval_file[str(qid)]["context"]
        spans = eval_file[str(qid)]["spans"]
        start_idx = spans[p1][0]
        end_idx = spans[p2][1]
        answer_dict[str(qid)] = context[start_idx: end_idx]
    return answer_dict


def evaluate(eval_file, answer_dict):
    f1 = exact_match = total = 0
    for key, value in answer_dict.items():
        total += 1
        ground_truths = eval_file[key]["answers"]
        prediction = value
        exact_match += metric_max_over_ground_truths(
            exact_match_score, prediction, ground_truths)
        f1 += metric_max_over_ground_truths(f1_score,
                                            prediction, ground_truths)
    exact_match = 100.0 * exact_match / total
    f1 = 100.0 * f1 / total
    return {'exact_match': exact_match, 'f1': f1}


def normalize_answer(s):

    def remove_articles(text):
        return re.sub(r'\b(a|an|the)\b', ' ', text)

    def white_space_fix(text):
        return ' '.join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def f1_score(prediction, ground_truth):
    prediction_tokens = normalize_answer(prediction).split()
    ground_truth_tokens = normalize_answer(ground_truth).split()
    common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0
    precision = 1.0 * num_same / len(prediction_tokens)
    recall = 1.0 * num_same / len(ground_truth_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1


def exact_match_score(prediction, ground_truth):
    return (normalize_answer(prediction) == normalize_answer(ground_truth))


def metric_max_over_ground_truths(metric_fn, prediction, ground_truths):
    scores_for_ground_truths = []
    for ground_truth in ground_truths:
        score = metric_fn(prediction, ground_truth)
        scores_for_ground_truths.append(score)
    return max(scores_for_ground_truths)